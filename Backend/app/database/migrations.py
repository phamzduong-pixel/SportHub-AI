from sqlalchemy import inspect, text

BASE_BOOKING_COLUMNS = {
    'id', 'booking_code', 'customer_id', 'field_id', 'time_slot_id',
    'booking_date', 'start_time_snapshot', 'end_time_snapshot',
    'price_snapshot', 'total_amount', 'status', 'note', 'created_at', 'updated_at',
}

def migrate_empty_legacy_booking_schema(engine):
    """Nâng schema booking cũ và bổ sung cơ chế giữ chỗ mà không làm mất dữ liệu."""
    inspector = inspect(engine)
    if 'bookings' not in inspector.get_table_names():
        return
    columns = {column['name'] for column in inspector.get_columns('bookings')}
    if not BASE_BOOKING_COLUMNS.issubset(columns):
        with engine.begin() as connection:
            booking_count = connection.execute(text('SELECT COUNT(*) FROM bookings')).scalar_one()
            usage_count = 0
            if 'booking_time_slots' in inspector.get_table_names():
                usage_count = connection.execute(text('SELECT COUNT(*) FROM booking_time_slots')).scalar_one()
            if booking_count or usage_count:
                raise RuntimeError('Schema bookings cũ đang có dữ liệu; cần migration thủ công trước khi khởi động.')
            if 'booking_time_slots' in inspector.get_table_names():
                connection.execute(text('DROP TABLE booking_time_slots'))
            connection.execute(text('DROP TABLE bookings'))
        return
    with engine.begin() as connection:
        if 'hold_expires_at' not in columns:
            column_type = 'TIMESTAMP WITH TIME ZONE' if engine.dialect.name == 'postgresql' else 'DATETIME'
            connection.execute(text(f'ALTER TABLE bookings ADD COLUMN hold_expires_at {column_type} NULL'))
        connection.execute(text("UPDATE bookings SET status='pending_confirmation' WHERE status='pending'"))
        connection.execute(text('DROP INDEX IF EXISTS uq_open_booking_slot_date'))
        condition = "status IN ('pending_payment', 'pending_confirmation', 'confirmed')"
        connection.execute(text(
            'CREATE UNIQUE INDEX IF NOT EXISTS uq_open_booking_slot_date '
            f'ON bookings (field_id, booking_date, time_slot_id) WHERE {condition}'
        ))


def migrate_field_recommendation_columns(engine):
    """Bổ sung metadata phục vụ recommendation mà không làm mất sân hiện có."""
    inspector = inspect(engine)
    if 'fields' not in inspector.get_table_names():
        return
    columns = {column['name'] for column in inspector.get_columns('fields')}
    with engine.begin() as connection:
        if 'rating' not in columns:
            connection.execute(text('ALTER TABLE fields ADD COLUMN rating FLOAT NOT NULL DEFAULT 0'))
        if 'review_count' not in columns:
            connection.execute(text('ALTER TABLE fields ADD COLUMN review_count INTEGER NOT NULL DEFAULT 0'))
        if 'distance_km' not in columns:
            connection.execute(text('ALTER TABLE fields ADD COLUMN distance_km FLOAT NULL'))


def migrate_user_profile_columns(engine):
    inspector = inspect(engine)
    if 'users' not in inspector.get_table_names():
        return
    columns = {column['name'] for column in inspector.get_columns('users')}
    if 'avatar_url' not in columns:
        with engine.begin() as connection:
            connection.execute(text('ALTER TABLE users ADD COLUMN avatar_url VARCHAR(500) NULL'))


def migrate_system_roles(engine):
    """Normalize platform roles while preserving MANAGER ownership and pending requests."""
    with engine.begin() as connection:
        inspector = inspect(connection)
        tables = set(inspector.get_table_names())
        if 'users' in tables:
            user_columns = {column['name'] for column in inspector.get_columns('users')}
            if 'owner_id' not in user_columns:
                connection.execute(text('ALTER TABLE users ADD COLUMN owner_id INTEGER NULL REFERENCES users(id)'))
            if 'management_permissions' not in user_columns:
                connection.execute(text("ALTER TABLE users ADD COLUMN management_permissions JSON NOT NULL DEFAULT '[]'"))
            connection.execute(text("UPDATE users SET role='SYSTEM_ADMIN' WHERE role='ADMIN'"))
            if 'owner_applications' in tables:
                application_columns = {column['name'] for column in inspector.get_columns('owner_applications')}
                created_column = ',created_at' if 'created_at' in application_columns else ''
                created_value = ',CURRENT_TIMESTAMP' if 'created_at' in application_columns else ''
                connection.execute(text(
                    f"INSERT INTO owner_applications (customer_id,status,representative,venue,legal_confirmed,submitted_at,updated_at{created_column}) "
                    f"SELECT id,'PENDING','{{}}','{{}}',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP{created_value} FROM users "
                    "WHERE role='OWNER_PENDING' AND NOT EXISTS (SELECT 1 FROM owner_applications a WHERE a.customer_id=users.id)"
                ))
                connection.execute(text("UPDATE users SET role='CUSTOMER' WHERE role='OWNER_PENDING'"))
            connection.execute(text("UPDATE users SET owner_id=NULL WHERE role!='MANAGER' AND owner_id IS NOT NULL"))
            connection.execute(text('CREATE INDEX IF NOT EXISTS ix_users_owner_id ON users (owner_id)'))
        if 'facilities' in tables:
            columns = {column['name'] for column in inspector.get_columns('facilities')}
            if 'is_active' not in columns:
                connection.execute(text('ALTER TABLE facilities ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1'))
            connection.execute(text('CREATE INDEX IF NOT EXISTS ix_facilities_is_active ON facilities (is_active)'))


def migrate_ownership_columns(engine):
    """Add tenant ownership and attach legacy rows to the first configured owner."""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    with engine.begin() as connection:
        if 'fields' in tables:
            field_columns = {column['name'] for column in inspector.get_columns('fields')}
            if 'owner_id' not in field_columns:
                connection.execute(text('ALTER TABLE fields ADD COLUMN owner_id INTEGER NULL REFERENCES users(id)'))
            connection.execute(text(
                "UPDATE fields SET owner_id=(SELECT id FROM users WHERE role='OWNER' ORDER BY id LIMIT 1) "
                "WHERE owner_id IS NULL"
            ))
            connection.execute(text('CREATE INDEX IF NOT EXISTS ix_fields_owner_id ON fields (owner_id)'))


def migrate_deposit_payment_schema(engine):
    """Add deposit snapshots without rewriting existing booking/payment history."""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    definitions = {
        'fields': {
            'deposit_type': "VARCHAR(20) NOT NULL DEFAULT 'percentage'",
            'deposit_value': 'NUMERIC(12,2) NOT NULL DEFAULT 30',
            'cancellation_policy': "VARCHAR(30) NOT NULL DEFAULT 'manual_review'",
            'cancellation_refund_percent': 'NUMERIC(5,2) NULL',
        },
        'bookings': {
            'deposit_type': "VARCHAR(20) NOT NULL DEFAULT 'percentage'",
            'deposit_value': 'NUMERIC(12,2) NOT NULL DEFAULT 30',
            'deposit_amount': 'NUMERIC(12,2) NOT NULL DEFAULT 0',
            'paid_amount': 'NUMERIC(12,2) NOT NULL DEFAULT 0',
            'remaining_amount': 'NUMERIC(12,2) NOT NULL DEFAULT 0',
            'payment_status': "VARCHAR(20) NOT NULL DEFAULT 'unpaid'",
            'cancellation_policy': "VARCHAR(30) NOT NULL DEFAULT 'manual_review'",
            'cancellation_refund_percent': 'NUMERIC(5,2) NULL',
            'refundable_deposit_amount': 'NUMERIC(12,2) NULL',
            'refund_status': "VARCHAR(20) NOT NULL DEFAULT 'not_requested'",
        },
        'payments': {
            'total_amount': 'NUMERIC(12,2) NOT NULL DEFAULT 0',
            'deposit_amount': 'NUMERIC(12,2) NOT NULL DEFAULT 0',
            'remaining_amount': 'NUMERIC(12,2) NOT NULL DEFAULT 0',
            'paid_amount': 'NUMERIC(12,2) NOT NULL DEFAULT 0',
            'payment_status': "VARCHAR(20) NOT NULL DEFAULT 'pending'",
            'bank_id': 'VARCHAR(30) NULL',
            'bank_name': 'VARCHAR(120) NULL',
            'bank_account_no': 'VARCHAR(50) NULL',
            'bank_account_name': 'VARCHAR(150) NULL',
            'transfer_content': 'VARCHAR(80) NULL',
            'qr_url': 'VARCHAR(1000) NULL',
            'expires_at': 'DATETIME NULL',
            'provider_reference': 'VARCHAR(120) NULL',
            'verification_source': 'VARCHAR(30) NULL',
            'refund_status': "VARCHAR(20) NOT NULL DEFAULT 'not_requested'",
        },
    }
    with engine.begin() as connection:
        for table, columns in definitions.items():
            if table not in tables:
                continue
            existing = {column['name'] for column in inspect(engine).get_columns(table)}
            for name, ddl in columns.items():
                if name not in existing:
                    connection.execute(text(f'ALTER TABLE {table} ADD COLUMN {name} {ddl}'))
        if 'bookings' in tables:
            connection.execute(text("UPDATE bookings SET remaining_amount=total_amount-paid_amount WHERE remaining_amount=0 AND total_amount>paid_amount"))
        if 'payments' in tables:
            connection.execute(text(
                'CREATE UNIQUE INDEX IF NOT EXISTS uq_pending_payment_per_booking '
                "ON payments (booking_id) WHERE status = 'pending'"
            ))
            connection.execute(text('CREATE UNIQUE INDEX IF NOT EXISTS ix_payments_transfer_content ON payments (transfer_content)'))
            connection.execute(text('CREATE UNIQUE INDEX IF NOT EXISTS ix_payments_provider_reference ON payments (provider_reference)'))


def migrate_professional_booking_schema(engine):
    """Add facility, lifecycle, cancellation and tenant-aware payment data in place."""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    timestamp = 'TIMESTAMP WITH TIME ZONE' if engine.dialect.name == 'postgresql' else 'DATETIME'
    definitions = {
        'facilities': {
            'contact_phone': 'VARCHAR(20) NULL',
            'opening_time': 'TIME NULL',
            'closing_time': 'TIME NULL',
            'amenities': "JSON NOT NULL DEFAULT '[]'",
            'image_urls': "JSON NOT NULL DEFAULT '[]'",
            'free_cancellation_minutes': 'INTEGER NOT NULL DEFAULT 360',
        },
        'time_slots': {
            'weekday_price': 'NUMERIC(12,2) NULL',
            'weekend_price': 'NUMERIC(12,2) NULL',
        },
        'fields': {'facility_id': 'INTEGER NULL REFERENCES facilities(id)'},
        'bookings': {
            'facility_id': 'INTEGER NULL REFERENCES facilities(id)',
            'facility_name_snapshot': 'VARCHAR(160) NULL',
            'refund_amount': 'NUMERIC(12,2) NOT NULL DEFAULT 0',
            'credit_amount': 'NUMERIC(12,2) NOT NULL DEFAULT 0',
            'additional_payment_required': 'NUMERIC(12,2) NOT NULL DEFAULT 0',
            'cancellation_reason': 'TEXT NULL',
            'cancelled_at': f'{timestamp} NULL',
            'cancelled_by': 'INTEGER NULL REFERENCES users(id)',
            'free_cancellation_minutes': 'INTEGER NOT NULL DEFAULT 360',
            'rescheduled_at': f'{timestamp} NULL',
        },
        'payments': {
            'customer_id': 'INTEGER NULL REFERENCES users(id)',
            'owner_id': 'INTEGER NULL REFERENCES users(id)',
            'provider': 'VARCHAR(80) NULL',
            'failed_reason': 'TEXT NULL',
            'refunded_at': f'{timestamp} NULL',
            'escrow_status': "VARCHAR(20) NOT NULL DEFAULT 'pending'",
        },
    }
    # This runs once before and once after create_all on legacy databases.
    # Delay facility foreign keys until the referenced table exists.
    if 'facilities' not in tables:
        definitions['fields'].pop('facility_id', None)
        definitions['bookings'].pop('facility_id', None)
    with engine.begin() as connection:
        for table, columns in definitions.items():
            if table not in tables:
                continue
            existing = {column['name'] for column in inspect(engine).get_columns(table)}
            for name, ddl in columns.items():
                if name not in existing:
                    connection.execute(text(f'ALTER TABLE {table} ADD COLUMN {name} {ddl}'))
        if 'bookings' in tables:
            connection.execute(text('DROP INDEX IF EXISTS uq_open_booking_slot_date'))
            condition = "status IN ('pending_payment', 'pending_confirmation', 'confirmed', 'in_progress')"
            connection.execute(text(
                'CREATE UNIQUE INDEX IF NOT EXISTS uq_open_booking_slot_date '
                f'ON bookings (field_id, booking_date, time_slot_id) WHERE {condition}'
            ))
        if 'payments' in tables:
            connection.execute(text("UPDATE payments SET payment_type='remaining' WHERE payment_type='full'"))
            connection.execute(text(
                "UPDATE payments SET escrow_status=CASE "
                "WHEN status='refunded' OR refund_status='refunded' THEN 'refunded' "
                "WHEN status='paid' THEN 'held' WHEN status IN ('failed','cancelled') THEN 'failed' ELSE 'pending' END "
                "WHERE escrow_status IS NULL OR escrow_status='pending'"
            ))
            connection.execute(text(
                "UPDATE payments SET escrow_status='released' WHERE status='paid' AND payment_type!='refund' "
                "AND booking_id IN (SELECT id FROM bookings WHERE status IN ('completed','no_show'))"
            ))

    tables = set(inspect(engine).get_table_names())
    if not {'facilities', 'fields', 'users'}.issubset(tables):
        return
    default_rules = '[{"min_minutes_before":360,"refund_percent":100},{"min_minutes_before":0,"refund_percent":0}]'
    with engine.begin() as connection:
        connection.execute(text(
            'INSERT INTO facilities (owner_id, name, location, cancellation_rules, legacy_field_id, created_at, updated_at) '
            'SELECT f.owner_id, f.name, f.location, :rules, f.id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP '
            'FROM fields f WHERE f.owner_id IS NOT NULL AND f.facility_id IS NULL '
            'AND NOT EXISTS (SELECT 1 FROM facilities x WHERE x.legacy_field_id=f.id)'
        ), {'rules': default_rules})
        connection.execute(text(
            'UPDATE fields SET facility_id=(SELECT id FROM facilities WHERE legacy_field_id=fields.id) '
            'WHERE facility_id IS NULL'
        ))
        if 'bookings' in tables:
            connection.execute(text(
                'UPDATE bookings SET facility_id=(SELECT facility_id FROM fields WHERE fields.id=bookings.field_id) '
                'WHERE facility_id IS NULL'
            ))
            connection.execute(text(
                'UPDATE bookings SET facility_name_snapshot=(SELECT name FROM facilities WHERE facilities.id=bookings.facility_id) '
                'WHERE facility_name_snapshot IS NULL'
            ))
        if 'payments' in tables:
            connection.execute(text(
                'UPDATE payments SET customer_id=(SELECT customer_id FROM bookings WHERE bookings.id=payments.booking_id) '
                'WHERE customer_id IS NULL'
            ))
            connection.execute(text(
                'UPDATE payments SET owner_id=(SELECT fields.owner_id FROM fields JOIN bookings ON bookings.field_id=fields.id WHERE bookings.id=payments.booking_id) '
                'WHERE owner_id IS NULL'
            ))
        connection.execute(text('CREATE INDEX IF NOT EXISTS ix_fields_facility_id ON fields (facility_id)'))
        if 'bookings' in tables:
            connection.execute(text('CREATE INDEX IF NOT EXISTS ix_bookings_facility_id ON bookings (facility_id)'))
        if 'payments' in tables:
            connection.execute(text('CREATE INDEX IF NOT EXISTS ix_payments_customer_id ON payments (customer_id)'))
            connection.execute(text('CREATE INDEX IF NOT EXISTS ix_payments_owner_id ON payments (owner_id)'))


def migrate_refund_workflow_schema(engine):
    """Normalize legacy owner rejections after the refund workflow tables exist."""
    tables = set(inspect(engine).get_table_names())
    if 'bookings' not in tables:
        return
    with engine.begin() as connection:
        connection.execute(text(
            "UPDATE bookings SET status='cancelled_by_owner' "
            "WHERE status='rejected' AND (paid_amount > 0 OR refund_status IN ('refund_pending','refunded','refund_overdue','disputed'))"
        ))


def migrate_partner_application_schema(engine):
    """Upgrade the existing OwnerApplication table without creating a parallel partner flow."""
    inspector = inspect(engine)
    if 'owner_applications' not in inspector.get_table_names():
        return
    columns = {column['name'] for column in inspector.get_columns('owner_applications')}
    timestamp = 'TIMESTAMP WITH TIME ZONE' if engine.dialect.name == 'postgresql' else 'DATETIME'

    # Applications used to be one-row-per-customer. Reapplication after a withdrawal
    # requires immutable historical rows, so remove only that legacy uniqueness rule.
    unique_customer = any(
        set(constraint.get('column_names') or []) == {'customer_id'}
        for constraint in inspector.get_unique_constraints('owner_applications')
    )
    if unique_customer and engine.dialect.name == 'sqlite':
        ordered_columns = [column['name'] for column in inspector.get_columns('owner_applications')]
        connection = engine.connect()
        try:
            connection.exec_driver_sql('PRAGMA foreign_keys=OFF')
            connection.commit()
            with connection.begin():
                connection.execute(text(f'''CREATE TABLE owner_applications_new (
                    id INTEGER NOT NULL PRIMARY KEY,
                    customer_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    status VARCHAR(20) NOT NULL,
                    representative JSON NOT NULL,
                    venue JSON NOT NULL,
                    legal_confirmed BOOLEAN NOT NULL,
                    rejection_reason TEXT NULL,
                    admin_note TEXT NULL,
                    document_path VARCHAR(500) NULL,
                    document_mime VARCHAR(50) NULL,
                    document_original_name VARCHAR(255) NULL,
                    document_size INTEGER NULL,
                    document_uploaded_at {timestamp} NULL,
                    reviewed_by INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,
                    submitted_at {timestamp} NULL,
                    reviewed_at {timestamp} NULL,
                    created_at {timestamp} NULL,
                    updated_at {timestamp} NULL,
                    withdrawn_at {timestamp} NULL,
                    withdraw_reason TEXT NULL
                )'''))
                target_columns = ordered_columns + [name for name in ('withdrawn_at', 'withdraw_reason') if name not in columns]
                select_values = ordered_columns + ['NULL' for name in ('withdrawn_at', 'withdraw_reason') if name not in columns]
                connection.execute(text(
                    f"INSERT INTO owner_applications_new ({','.join(target_columns)}) "
                    f"SELECT {','.join(select_values)} FROM owner_applications"
                ))
                connection.execute(text('DROP TABLE owner_applications'))
                connection.execute(text('ALTER TABLE owner_applications_new RENAME TO owner_applications'))
                connection.execute(text("UPDATE owner_applications SET status='PENDING_REVIEW' WHERE status='PENDING'"))
                connection.execute(text('UPDATE owner_applications SET created_at=COALESCE(created_at, submitted_at, updated_at, CURRENT_TIMESTAMP) WHERE created_at IS NULL'))
                connection.execute(text('CREATE INDEX IF NOT EXISTS ix_owner_applications_customer_id ON owner_applications (customer_id)'))
                connection.execute(text('CREATE INDEX IF NOT EXISTS ix_owner_applications_status ON owner_applications (status)'))
            connection.exec_driver_sql('PRAGMA foreign_keys=ON')
            connection.commit()
        finally:
            connection.close()
        return

    with engine.begin() as connection:
        if unique_customer and engine.dialect.name == 'postgresql':
            for constraint in inspector.get_unique_constraints('owner_applications'):
                if set(constraint.get('column_names') or []) == {'customer_id'} and constraint.get('name'):
                    connection.execute(text(f'ALTER TABLE owner_applications DROP CONSTRAINT "{constraint["name"]}"'))
        if 'admin_note' not in columns:
            connection.execute(text('ALTER TABLE owner_applications ADD COLUMN admin_note TEXT NULL'))
        if 'created_at' not in columns:
            connection.execute(text(f'ALTER TABLE owner_applications ADD COLUMN created_at {timestamp} NULL'))
            connection.execute(text('UPDATE owner_applications SET created_at=COALESCE(submitted_at, updated_at, CURRENT_TIMESTAMP) WHERE created_at IS NULL'))
        document_columns = {
            'document_path': 'VARCHAR(500) NULL', 'document_mime': 'VARCHAR(50) NULL',
            'document_original_name': 'VARCHAR(255) NULL', 'document_size': 'INTEGER NULL',
            'document_uploaded_at': f'{timestamp} NULL',
        }
        for name, ddl in document_columns.items():
            if name not in columns:
                connection.execute(text(f'ALTER TABLE owner_applications ADD COLUMN {name} {ddl}'))
        if 'withdrawn_at' not in columns:
            connection.execute(text(f'ALTER TABLE owner_applications ADD COLUMN withdrawn_at {timestamp} NULL'))
        if 'withdraw_reason' not in columns:
            connection.execute(text('ALTER TABLE owner_applications ADD COLUMN withdraw_reason TEXT NULL'))
        connection.execute(text("UPDATE owner_applications SET status='PENDING_REVIEW' WHERE status='PENDING'"))
