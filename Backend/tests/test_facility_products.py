import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import get_password_hash
from app.database.base import Base
from app.database.demo_seed import seed_product_catalog
from app.database.session import get_db
from app.database.migrations import migrate_product_inventory_schema
from app.main import app
from app.models.facility import Facility
from app.models.field import Booking, Field
from app.models.product import BookingProductItem, FacilityProduct
from app.models.payment import Payment
from app.services.inventory_service import InventoryService
from app.models.time_slot import TimeSlot
from app.models.user import User


class FacilityProductTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        self.Session = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        Base.metadata.create_all(self.engine)
        with self.Session() as db:
            seed_product_catalog(db); db.commit()
            owner_a = User(full_name='Owner A', email='product-owner-a@test.local', hashed_password=get_password_hash('Owner@123'), role='OWNER')
            owner_b = User(full_name='Owner B', email='product-owner-b@test.local', hashed_password=get_password_hash('Owner@123'), role='OWNER')
            customer = User(full_name='Customer', email='product-customer@test.local', hashed_password=get_password_hash('Customer@123'), role='CUSTOMER')
            db.add_all([owner_a, owner_b, customer]); db.flush()
            facility_a = Facility(owner_id=owner_a.id, name='Cơ sở A', location='Hà Nội', sports=['Cầu lông'])
            facility_b = Facility(owner_id=owner_b.id, name='Cơ sở B', location='Đà Nẵng', sports=['Tennis'])
            db.add_all([facility_a, facility_b]); db.flush()
            field = Field(owner_id=owner_a.id, facility_id=facility_a.id, name='Sân A', sport_type='Cầu lông', location='Hà Nội', capacity=4, base_price=200000, amenities=[])
            db.add(field); db.flush()
            slot = TimeSlot(field_id=field.id, name='Ca sáng', start_time=time(8), end_time=time(9), price=200000)
            db.add(slot); db.commit()
            self.customer_id = customer.id
            self.owner_a_id = owner_a.id
            self.facility_a_id, self.facility_b_id = facility_a.id, facility_b.id
            self.field_id, self.slot_id = field.id, slot.id

        def override_db():
            with self.Session() as db:
                yield db
        app.dependency_overrides[get_db] = override_db
        self.client = TestClient(app)
        self.owner_a = self.login('product-owner-a@test.local', 'Owner@123')
        self.owner_b = self.login('product-owner-b@test.local', 'Owner@123')
        self.customer = self.login('product-customer@test.local', 'Customer@123')

    def tearDown(self):
        self.client.close(); app.dependency_overrides.clear(); Base.metadata.drop_all(self.engine)

    def login(self, email, password):
        response = self.client.post('/auth/login', json={'email': email, 'password': password})
        self.assertEqual(response.status_code, 200, response.text)
        return {'Authorization': f"Bearer {response.json()['access_token']}"}

    def payload(self, **changes):
        return {
            'facility_id': self.facility_a_id, 'name': 'Cho thuê vợt', 'product_type': 'RENT',
            'description': 'Vợt tiêu chuẩn', 'image_url': 'https://example.com/racket.jpg',
            'price': 50000, 'unit': 'giờ', 'sports': ['Cầu lông', 'Pickleball'], 'status': 'ACTIVE', **changes,
        }

    def create_product(self, **changes):
        response = self.client.post('/facility-products', headers=self.owner_a, json=self.payload(**changes))
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_owner_crud_filters_status_price_and_sports(self):
        product = self.create_product(sports=['Cầu lông', 'cầu lông', 'Pickleball'])
        self.assertEqual(product['sports'], ['Cầu lông', 'Pickleball'])
        self.assertFalse(product['has_booking_history'])
        filtered = self.client.get('/facility-products?product_type=RENT&status=ACTIVE&search=vợt', headers=self.owner_a)
        self.assertEqual([item['id'] for item in filtered.json()], [product['id']])
        price = self.client.patch(f"/facility-products/{product['id']}/price", headers=self.owner_a, json={'price': 75000})
        self.assertEqual(price.json()['price'], 75000)
        disabled = self.client.patch(f"/facility-products/{product['id']}/status", headers=self.owner_a, json={'is_active': False})
        self.assertEqual(disabled.json()['status'], 'INACTIVE')
        updated = self.client.put(f"/facility-products/{product['id']}", headers=self.owner_a, json=self.payload(name='Dịch vụ thuê vợt', product_type='SERVICE', status='ACTIVE'))
        self.assertEqual(updated.json()['product_type'], 'SERVICE')

    def test_court_service_configuration_filters_and_unassigns_one_sport(self):
        product = self.create_product(sports=['Cầu lông', 'Pickleball'])
        badminton = self.client.get(
            '/facility-products', params={'facility_id': self.facility_a_id, 'sport': 'Badminton'},
            headers=self.owner_a,
        )
        self.assertEqual(badminton.status_code, 200, badminton.text)
        self.assertEqual([item['id'] for item in badminton.json()], [product['id']])
        tennis = self.client.get(
            '/facility-products', params={'facility_id': self.facility_a_id, 'sport': 'Tennis'},
            headers=self.owner_a,
        )
        self.assertEqual(tennis.json(), [])

        endpoint = f"/facility-products/{product['id']}/sports"
        self.assertEqual(self.client.delete(endpoint, params={'sport': 'Cầu lông'}, headers=self.customer).status_code, 403)
        self.assertEqual(self.client.delete(endpoint, params={'sport': 'Cầu lông'}, headers=self.owner_b).status_code, 404)
        detached = self.client.delete(endpoint, params={'sport': 'Badminton'}, headers=self.owner_a)
        self.assertEqual(detached.status_code, 200, detached.text)
        self.assertEqual(detached.json()['sports'], ['Pickleball'])
        self.assertEqual(detached.json()['status'], 'ACTIVE')
        archived = self.client.delete(endpoint, params={'sport': 'Pickleball'}, headers=self.owner_a)
        self.assertEqual(archived.status_code, 200, archived.text)
        self.assertEqual(archived.json()['sports'], [])
        self.assertEqual(archived.json()['status'], 'ARCHIVED')

    def test_owner_isolation_and_customer_forbidden(self):
        product = self.create_product()
        self.assertEqual(self.client.get('/facility-products', headers=self.owner_b).json(), [])
        self.assertEqual(self.client.patch(f"/facility-products/{product['id']}/price", headers=self.owner_b, json={'price': 1}).status_code, 404)
        self.assertEqual(self.client.post('/facility-products', headers=self.customer, json=self.payload()).status_code, 403)
        self.assertEqual(self.client.post('/facility-products', headers=self.owner_a, json=self.payload(facility_id=self.facility_b_id)).status_code, 404)

    def test_validation_requires_sport_and_unused_product_is_soft_deleted(self):
        invalid = self.client.post('/facility-products', headers=self.owner_a, json=self.payload(sports=[]))
        self.assertEqual(invalid.status_code, 422)
        product = self.create_product(name='Nước suối', product_type='SELL', unit='chai')
        deleted = self.client.delete(f"/facility-products/{product['id']}", headers=self.owner_a)
        self.assertEqual(deleted.json()['action'], 'archived')
        with self.Session() as db:
            self.assertEqual(db.get(FacilityProduct, product['id']).status, 'ARCHIVED')

    def test_product_used_in_booking_is_archived_not_hard_deleted(self):
        product = self.create_product()
        with self.Session() as db:
            booking = Booking(
                booking_code='PRODUCT-HISTORY', customer_id=self.customer_id, facility_id=self.facility_a_id,
                field_id=self.field_id, time_slot_id=self.slot_id, booking_date=date.today() + timedelta(days=3),
                start_time_snapshot=time(8), end_time_snapshot=time(9), price_snapshot=200000,
                total_amount=250000, deposit_amount=75000, remaining_amount=250000,
            )
            db.add(booking); db.flush()
            db.add(BookingProductItem(
                booking_id=booking.id, product_id=product['id'], product_name_snapshot=product['name'],
                product_type_snapshot=product['product_type'], unit_snapshot=product['unit'],
                unit_price_snapshot=Decimal('50000'), quantity=1, line_total=Decimal('50000'),
            ))
            db.commit()
        archived = self.client.delete(f"/facility-products/{product['id']}", headers=self.owner_a)
        self.assertEqual(archived.status_code, 200, archived.text)
        self.assertEqual(archived.json()['action'], 'archived')
        self.assertEqual(archived.json()['product']['status'], 'ARCHIVED')
        self.assertTrue(archived.json()['product']['has_booking_history'])
        with self.Session() as db:
            self.assertIsNotNone(db.get(FacilityProduct, product['id']))

    def make_booking_item(self, product, quantity=2):
        with self.Session() as db:
            booking = Booking(
                booking_code=f"INV-{product['product_type']}-{product['id']}", customer_id=self.customer_id,
                facility_id=self.facility_a_id, field_id=self.field_id, time_slot_id=self.slot_id,
                booking_date=date.today() + timedelta(days=4 + product['id']), start_time_snapshot=time(8), end_time_snapshot=time(9),
                price_snapshot=200000, total_amount=200000, deposit_amount=60000, remaining_amount=200000,
            )
            db.add(booking); db.flush()
            item = BookingProductItem(
                booking_id=booking.id, product_id=product['id'], product_name_snapshot=product['name'],
                product_type_snapshot=product['product_type'], unit_snapshot=product['unit'],
                unit_price_snapshot=Decimal(str(product['price'])), quantity=quantity,
                line_total=Decimal(str(product['price'])) * quantity,
            )
            db.add(item); db.commit(); return item.id

    def make_active_booking(self, *, status='in_progress', paid_amount=60000):
        with self.Session() as db:
            booking = Booking(
                booking_code=f'DURING-{status}-{datetime.now().timestamp()}',
                customer_id=self.customer_id, facility_id=self.facility_a_id,
                field_id=self.field_id, time_slot_id=self.slot_id,
                booking_date=date.today(), start_time_snapshot=time(8), end_time_snapshot=time(9),
                price_snapshot=200000, court_amount=200000, service_amount=0,
                total_amount=200000, deposit_amount=60000, paid_amount=paid_amount,
                remaining_amount=140000, payment_status='partial', status=status,
            )
            db.add(booking); db.flush()
            if paid_amount:
                db.add(Payment(
                    booking_id=booking.id, customer_id=self.customer_id, owner_id=self.owner_a_id,
                    transaction_code=f'DEP-{booking.id}-{datetime.now().timestamp()}', amount=paid_amount,
                    total_amount=200000, deposit_amount=60000, remaining_amount=140000,
                    paid_amount=paid_amount, payment_status='paid', payment_method='mock_online',
                    payment_type='deposit', status='paid', escrow_status='held', paid_at=datetime.now(timezone.utc),
                ))
            db.commit(); return booking.id

    def field_sport(self):
        with self.Session() as db:
            return db.get(Field, self.field_id).sport_type

    def test_catalog_suggestions_are_owner_only_and_do_not_seed_products(self):
        before = self.client.get('/facility-products', headers=self.owner_a).json()
        catalog = self.client.get('/facility-products/catalog?sport=futsal', headers=self.owner_a)
        self.assertEqual(catalog.status_code, 200, catalog.text)
        self.assertGreater(len(catalog.json()), 8)
        self.assertTrue(any(item['product_type'] == 'RENT' for item in catalog.json()))
        self.assertEqual(self.client.get('/facility-products/catalog?sport=Tennis', headers=self.customer).status_code, 403)
        self.assertEqual(self.client.get('/facility-products', headers=self.owner_a).json(), before)

    def test_owner_can_import_multiple_catalog_items_without_duplicates(self):
        catalog = self.client.get('/facility-products/catalog?sport=Pickleball', headers=self.owner_a)
        self.assertEqual(catalog.status_code, 200, catalog.text)
        selected = catalog.json()[:3]
        payload = {
            'facility_id': self.facility_a_id, 'sport': self.field_sport(),
            'catalog_keys': [item['key'] for item in selected],
        }
        imported = self.client.post('/facility-products/from-catalog', headers=self.owner_a, json=payload)
        self.assertEqual(imported.status_code, 422, imported.text)

        badminton_catalog = self.client.get(
            f'/facility-products/catalog?sport={self.field_sport()}', headers=self.owner_a,
        ).json()
        payload['catalog_keys'] = [item['key'] for item in badminton_catalog[:3]]
        first = self.client.post('/facility-products/from-catalog', headers=self.owner_a, json=payload)
        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual(len(first.json()), 3)
        self.assertTrue(all(item['facility_id'] == self.facility_a_id for item in first.json()))
        self.assertTrue(all(item['status'] == 'INACTIVE' and item['price'] == 0 for item in first.json()))
        second = self.client.post('/facility-products/from-catalog', headers=self.owner_a, json=payload)
        self.assertEqual(second.status_code, 201, second.text)
        self.assertEqual({item['id'] for item in first.json()}, {item['id'] for item in second.json()})
        with self.Session() as db:
            self.assertEqual(db.query(FacilityProduct).count(), 3)
        self.assertEqual(self.client.post('/facility-products/from-catalog', headers=self.customer, json=payload).status_code, 403)
        self.assertEqual(self.client.post('/facility-products/from-catalog', headers=self.owner_b, json=payload).status_code, 404)

    def test_owner_booking_options_filter_tenant_facility_sport_and_keep_out_of_stock_visible(self):
        available = self.create_product(
            name='Vợt theo booking', product_type='RENT', sports=['Badminton'],
            stock_quantity=4, track_inventory=True,
        )
        sold_out = self.create_product(
            name='Nước đã hết', product_type='SELL', unit='chai', sports=[self.field_sport()],
            stock_quantity=0, track_inventory=True,
        )
        service = self.create_product(
            name='Huấn luyện tại sân', product_type='SERVICE', unit='giờ', sports=[self.field_sport()],
            stock_quantity=0, track_inventory=False,
        )
        inactive = self.create_product(
            name='Dịch vụ đã tắt', product_type='SERVICE', sports=[self.field_sport()], status='INACTIVE',
        )
        wrong_sport = self.create_product(
            name='Chỉ cho tennis', product_type='RENT', sports=['Tennis'], stock_quantity=4, track_inventory=True,
        )
        other_owner = self.client.post('/facility-products', headers=self.owner_b, json=self.payload(
            facility_id=self.facility_b_id, name='Sản phẩm OWNER B', sports=[self.field_sport()],
            stock_quantity=10, track_inventory=True,
        ))
        self.assertEqual(other_owner.status_code, 201, other_owner.text)
        booking_id = self.make_active_booking()

        response = self.client.get(f'/bookings/{booking_id}/product-options', headers=self.owner_a)
        self.assertEqual(response.status_code, 200, response.text)
        options = {item['id']: item for item in response.json()}
        self.assertEqual(set(options), {available['id'], sold_out['id'], service['id']})
        self.assertTrue(options[available['id']]['is_available'])
        self.assertFalse(options[sold_out['id']]['is_available'])
        self.assertEqual(options[sold_out['id']]['available_quantity'], 0)
        self.assertTrue(options[service['id']]['is_available'])
        self.assertFalse(options[service['id']]['track_inventory'])
        self.assertNotIn(inactive['id'], options)
        self.assertNotIn(wrong_sport['id'], options)
        self.assertNotIn(other_owner.json()['id'], options)
        self.assertIn(self.client.get(f'/bookings/{booking_id}/product-options', headers=self.owner_b).status_code, (403, 404))
        self.assertEqual(self.client.get(f'/bookings/{booking_id}/product-options', headers=self.customer).status_code, 403)

        added_alias = self.client.post(
            f'/bookings/{booking_id}/products', headers=self.owner_a,
            json={'product_id': available['id'], 'quantity': 1},
        )
        self.assertEqual(added_alias.status_code, 201, added_alias.text)

    def test_owner_adds_updates_and_removes_during_usage_product_with_snapshot(self):
        product = self.create_product(
            name='NÆ°á»›c phÃ¡t sinh', product_type='SELL', unit='chai', price=25000,
            sports=[self.field_sport()], stock_quantity=3, track_inventory=True,
        )
        booking_id = self.make_active_booking()

        forbidden = self.client.post(
            f'/bookings/{booking_id}/products', headers=self.owner_b,
            json={'product_id': product['id'], 'quantity': 1},
        )
        self.assertIn(forbidden.status_code, (403, 404), forbidden.text)
        self.assertEqual(self.client.post(
            f'/bookings/{booking_id}/products', headers=self.customer,
            json={'product_id': product['id'], 'quantity': 1},
        ).status_code, 403)

        added = self.client.post(
            f'/bookings/{booking_id}/products', headers=self.owner_a,
            json={'product_id': product['id'], 'quantity': 2},
        )
        self.assertEqual(added.status_code, 201, added.text)
        data = added.json(); item = data['product_items'][0]
        self.assertEqual((item['source'], item['added_by_name']), ('OWNER_DURING_USAGE', 'Owner A'))
        self.assertIsNotNone(item['added_at'])
        self.assertEqual((item['unit_price'], item['subtotal']), (25000, 50000))
        self.assertEqual((data['court_amount'], data['service_amount'], data['total_amount']), (200000, 50000, 250000))
        self.assertEqual(data['deposit_amount'], 60000)
        self.assertEqual(data['remaining_amount'], 190000)
        with self.Session() as db:
            self.assertEqual(db.get(FacilityProduct, product['id']).reserved_quantity, 2)

        changed_price = self.client.patch(
            f"/facility-products/{product['id']}/price", headers=self.owner_a, json={'price': 99000},
        )
        self.assertEqual(changed_price.status_code, 200, changed_price.text)
        visible = self.client.get(f'/bookings/{booking_id}', headers=self.customer)
        self.assertEqual(visible.status_code, 200, visible.text)
        self.assertEqual(visible.json()['product_items'][0]['unit_price'], 25000)

        too_many = self.client.patch(
            f"/bookings/{booking_id}/products/{item['item_id']}", headers=self.owner_a,
            json={'quantity': 4},
        )
        self.assertEqual(too_many.status_code, 409, too_many.text)
        with self.Session() as db:
            self.assertEqual(db.get(FacilityProduct, product['id']).reserved_quantity, 2)

        updated = self.client.patch(
            f"/bookings/{booking_id}/products/{item['item_id']}", headers=self.owner_a,
            json={'quantity': 1},
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()['product_items'][0]['unit_price'], 25000)
        self.assertEqual(updated.json()['service_amount'], 25000)
        self.assertEqual(updated.json()['deposit_amount'], 60000)
        with self.Session() as db:
            self.assertEqual(db.get(FacilityProduct, product['id']).reserved_quantity, 1)

        removed = self.client.delete(
            f"/bookings/{booking_id}/products/{item['item_id']}", headers=self.owner_a,
        )
        self.assertEqual(removed.status_code, 200, removed.text)
        self.assertEqual(removed.json()['product_items'], [])
        self.assertEqual((removed.json()['service_amount'], removed.json()['total_amount']), (0, 200000))
        self.assertEqual(removed.json()['deposit_amount'], 60000)
        with self.Session() as db:
            self.assertEqual(db.get(FacilityProduct, product['id']).reserved_quantity, 0)

    def test_during_usage_items_become_immutable_after_completion(self):
        product = self.create_product(
            name='Dá»‹ch vá»¥ phÃ¡t sinh', product_type='SERVICE', unit='lÆ°á»£t', price=30000,
            sports=[self.field_sport()], stock_quantity=2, track_inventory=True,
        )
        booking_id = self.make_active_booking()
        added = self.client.post(
            f'/bookings/{booking_id}/products', headers=self.owner_a,
            json={'product_id': product['id'], 'quantity': 1},
        )
        self.assertEqual(added.status_code, 201, added.text)
        item_id = added.json()['product_items'][0]['item_id']
        with self.Session() as db:
            booking = db.get(Booking, booking_id)
            booking.status = 'completed'
            db.commit()
        self.assertEqual(self.client.patch(
            f'/bookings/{booking_id}/products/{item_id}', headers=self.owner_a, json={'quantity': 2},
        ).status_code, 409)
        self.assertEqual(self.client.delete(
            f'/bookings/{booking_id}/products/{item_id}', headers=self.owner_a,
        ).status_code, 409)
        self.assertEqual(self.client.post(
            f'/bookings/{booking_id}/products', headers=self.owner_a,
            json={'product_id': product['id'], 'quantity': 1},
        ).status_code, 409)

    def test_inventory_adjustment_never_goes_negative_and_writes_history(self):
        product = self.create_product(stock_quantity=5, track_inventory=True)
        adjusted = self.client.patch(f"/facility-products/{product['id']}/inventory", headers=self.owner_a, json={
            'quantity_change': 4, 'note': 'Nhập thêm hàng',
        })
        self.assertEqual(adjusted.status_code, 200, adjusted.text)
        self.assertEqual(adjusted.json()['stock_quantity'], 9)
        self.assertEqual(adjusted.json()['available_quantity'], 9)
        invalid = self.client.patch(f"/facility-products/{product['id']}/inventory", headers=self.owner_a, json={
            'quantity_change': -10, 'note': 'Điều chỉnh sai',
        })
        self.assertEqual(invalid.status_code, 409)
        history = self.client.get(f"/facility-products/{product['id']}/inventory-history", headers=self.owner_a)
        self.assertEqual(history.status_code, 200, history.text)
        self.assertEqual(history.json()[0]['movement_type'], 'IMPORT')
        self.assertEqual(self.client.get(f"/facility-products/{product['id']}/inventory-history", headers=self.owner_b).status_code, 404)

    def test_sell_consumes_stock_and_rent_returns_to_available(self):
        sold = self.create_product(name='Nước', product_type='SELL', stock_quantity=10, track_inventory=True)
        sold_item_id = self.make_booking_item(sold, 2)
        with self.Session() as db:
            item = db.get(BookingProductItem, sold_item_id); inventory = InventoryService(db)
            inventory.reserve(item); db.flush()
            self.assertEqual((item.product.stock_quantity, item.product.reserved_quantity), (10, 2))
            inventory.fulfill(item); db.commit()
            self.assertEqual((item.product.stock_quantity, item.product.reserved_quantity, item.inventory_status), (8, 0, 'SOLD'))

        rented = self.create_product(name='Vợt thuê', product_type='RENT', stock_quantity=6, track_inventory=True)
        rented_item_id = self.make_booking_item(rented, 3)
        with self.Session() as db:
            item = db.get(BookingProductItem, rented_item_id); inventory = InventoryService(db)
            inventory.reserve(item); db.commit()
            self.assertEqual(item.product.available_quantity, 3)
        blocked = self.client.patch(f"/facility-products/{rented['id']}/inventory", headers=self.owner_a, json={
            'stock_quantity': 2, 'note': 'Không được thấp hơn lượng giữ',
        })
        self.assertEqual(blocked.status_code, 409)
        with self.Session() as db:
            item = db.get(BookingProductItem, rented_item_id); inventory = InventoryService(db)
            inventory.release(item, returned=True); db.commit()
            self.assertEqual((item.product.stock_quantity, item.product.reserved_quantity, item.inventory_status), (6, 0, 'RETURNED'))

        service = self.create_product(name='Khăn giới hạn', product_type='SERVICE', stock_quantity=4, track_inventory=True)
        service_item_id = self.make_booking_item(service, 2)
        with self.Session() as db:
            item = db.get(BookingProductItem, service_item_id); inventory = InventoryService(db)
            inventory.reserve(item); inventory.fulfill(item); db.commit()
            self.assertEqual((item.product.stock_quantity, item.product.reserved_quantity, item.inventory_status), (2, 0, 'CONSUMED'))

    def test_public_catalog_hides_out_of_stock_but_untracked_service_remains_available(self):
        out = self.create_product(name='Bóng bán', product_type='SELL', stock_quantity=0, track_inventory=True)
        service = self.create_product(name='Huấn luyện', product_type='SERVICE')
        self.assertFalse(out['is_available'])
        self.assertFalse(service['track_inventory'])
        available = self.client.get(f'/facility-products/available?facility_id={self.facility_a_id}').json()
        ids = {item['id'] for item in available}
        self.assertNotIn(out['id'], ids)
        self.assertIn(service['id'], ids)

    def test_booking_quote_and_create_use_authoritative_product_snapshot_and_reserve_stock(self):
        product = self.create_product(
            name='Vợt thi đấu', product_type='RENT', unit='cây',
            price=50000, sports=['Cầu lông'], stock_quantity=5, track_inventory=True,
        )
        booking_date = (date.today() + timedelta(days=10)).isoformat()
        quote = self.client.get('/bookings/quote', params=[
            ('field_id', self.field_id), ('time_slot_ids', self.slot_id), ('date', booking_date),
            ('product_id', product['id']), ('product_quantity', 2),
        ])
        self.assertEqual(quote.status_code, 200, quote.text)
        self.assertEqual(quote.json()['court_amount'], 200000)
        self.assertEqual(quote.json()['service_amount'], 100000)
        self.assertEqual(quote.json()['total_amount'], 300000)
        self.assertEqual(quote.json()['deposit_amount'], 60000)
        self.assertEqual(quote.json()['remaining_amount'], 240000)
        self.assertEqual(quote.json()['product_items'][0]['subtotal'], 100000)

        created = self.client.post('/bookings', headers=self.customer, json={
            'field_id': self.field_id, 'time_slot_ids': [self.slot_id],
            'booking_date': booking_date,
            'product_items': [{'product_id': product['id'], 'quantity': 2}],
        })
        self.assertEqual(created.status_code, 201, created.text)
        booking = created.json()
        self.assertEqual(booking['status'], 'pending_payment')
        self.assertEqual(booking['service_amount'], 100000)
        self.assertEqual(booking['product_items'][0]['name'], 'Vợt thi đấu')
        self.assertEqual(booking['product_items'][0]['inventory_status'], 'RESERVED')
        with self.Session() as db:
            stored_product = db.get(FacilityProduct, product['id'])
            self.assertEqual((stored_product.stock_quantity, stored_product.reserved_quantity), (5, 2))

        changed = self.client.patch(
            f"/facility-products/{product['id']}/price", headers=self.owner_a, json={'price': 99000},
        )
        self.assertEqual(changed.status_code, 200, changed.text)
        detail = self.client.get(f"/bookings/{booking['id']}", headers=self.customer)
        self.assertEqual(detail.json()['product_items'][0]['unit_price'], 50000)

        cancelled = self.client.patch(
            f"/bookings/{booking['id']}/cancel", headers=self.customer,
            json={'reason': 'Thay đổi kế hoạch'},
        )
        self.assertEqual(cancelled.status_code, 200, cancelled.text)
        with self.Session() as db:
            stored_product = db.get(FacilityProduct, product['id'])
            item = db.scalar(select(BookingProductItem).where(BookingProductItem.booking_id == booking['id']))
            self.assertEqual(stored_product.reserved_quantity, 0)
            self.assertEqual(item.inventory_status, 'RELEASED')

    def test_booking_rejects_unavailable_wrong_sport_and_duplicate_products(self):
        limited = self.create_product(
            name='Nước giới hạn', product_type='SELL', unit='chai',
            price=15000, sports=['Cầu lông'], stock_quantity=1, track_inventory=True,
        )
        wrong_sport = self.create_product(
            name='Bóng tennis', product_type='RENT', unit='ống',
            sports=['Tennis'], stock_quantity=10, track_inventory=True,
        )
        booking_date = (date.today() + timedelta(days=11)).isoformat()
        base = {
            'field_id': self.field_id, 'time_slot_ids': [self.slot_id], 'booking_date': booking_date,
        }
        too_many = self.client.post('/bookings', headers=self.customer, json={
            **base, 'product_items': [{'product_id': limited['id'], 'quantity': 2}],
        })
        self.assertEqual(too_many.status_code, 409, too_many.text)
        self.assertIn('chỉ còn 1', too_many.json()['detail'])
        unsupported = self.client.post('/bookings', headers=self.customer, json={
            **base, 'product_items': [{'product_id': wrong_sport['id'], 'quantity': 1}],
        })
        self.assertEqual(unsupported.status_code, 409, unsupported.text)
        duplicate = self.client.post('/bookings', headers=self.customer, json={
            **base, 'product_items': [
                {'product_id': limited['id'], 'quantity': 1},
                {'product_id': limited['id'], 'quantity': 1},
            ],
        })
        self.assertEqual(duplicate.status_code, 422, duplicate.text)

    def test_expired_pending_booking_releases_reserved_products(self):
        product = self.create_product(
            name='Khăn thuê', product_type='RENT', unit='chiếc',
            price=20000, sports=['Cầu lông'], stock_quantity=3, track_inventory=True,
        )
        created = self.client.post('/bookings', headers=self.customer, json={
            'field_id': self.field_id, 'time_slot_ids': [self.slot_id],
            'booking_date': (date.today() + timedelta(days=12)).isoformat(),
            'product_items': [{'product_id': product['id'], 'quantity': 2}],
        })
        self.assertEqual(created.status_code, 201, created.text)
        booking_id = created.json()['id']
        with self.Session() as db:
            booking = db.get(Booking, booking_id)
            booking.hold_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
            db.commit()
        listed = self.client.get('/bookings/my?page_size=100', headers=self.customer)
        self.assertEqual(listed.status_code, 200, listed.text)
        with self.Session() as db:
            booking = db.get(Booking, booking_id)
            stored_product = db.get(FacilityProduct, product['id'])
            item = db.scalar(select(BookingProductItem).where(BookingProductItem.booking_id == booking_id))
            self.assertEqual(booking.status, 'expired')
            self.assertEqual(stored_product.reserved_quantity, 0)
            self.assertEqual(item.inventory_status, 'RELEASED')

    def test_reschedule_revalidates_products_without_reserving_twice(self):
        product = self.create_product(
            name='Vợt giữ lịch', product_type='RENT', unit='cây',
            sports=['Cầu lông'], stock_quantity=2, track_inventory=True,
        )
        original_date = date.today() + timedelta(days=14)
        created = self.client.post('/bookings', headers=self.customer, json={
            'field_id': self.field_id, 'time_slot_ids': [self.slot_id],
            'booking_date': original_date.isoformat(),
            'product_items': [{'product_id': product['id'], 'quantity': 2}],
        })
        self.assertEqual(created.status_code, 201, created.text)
        booking_id = created.json()['id']
        with self.Session() as db:
            booking = db.get(Booking, booking_id)
            booking.status = 'confirmed'; booking.hold_expires_at = None
            tennis = Field(
                owner_id=booking.field.owner_id, facility_id=self.facility_a_id,
                name='Sân tennis', sport_type='Tennis', location='Hà Nội',
                capacity=4, base_price=250000, amenities=[],
            )
            db.add(tennis); db.flush()
            tennis_slot = TimeSlot(field_id=tennis.id, name='Ca tennis', start_time=time(9), end_time=time(10), price=250000)
            db.add(tennis_slot); db.commit()
            tennis_id, tennis_slot_id = tennis.id, tennis_slot.id
        invalid = self.client.post(f'/bookings/{booking_id}/reschedule/quote', headers=self.customer, json={
            'field_id': tennis_id, 'time_slot_ids': [tennis_slot_id],
            'booking_date': (original_date + timedelta(days=1)).isoformat(),
        })
        self.assertEqual(invalid.status_code, 409, invalid.text)
        self.assertIn('không áp dụng', invalid.json()['detail'])
        valid = self.client.patch(f'/bookings/{booking_id}/reschedule', headers=self.customer, json={
            'field_id': self.field_id, 'time_slot_ids': [self.slot_id],
            'booking_date': (original_date + timedelta(days=2)).isoformat(),
        })
        self.assertEqual(valid.status_code, 200, valid.text)
        with self.Session() as db:
            self.assertEqual(db.get(FacilityProduct, product['id']).reserved_quantity, 2)

    def test_ai_product_answer_uses_current_backend_price_and_quantity(self):
        product = self.create_product(
            name='Ống cầu thật', product_type='SELL', unit='ống', price=80000,
            sports=['Cầu lông'], stock_quantity=4, track_inventory=True,
        )
        answer = self.client.post('/ai/assistant', headers=self.customer, json={
            'message': 'Sản phẩm còn hàng và giá bao nhiêu?', 'context_field_id': self.field_id,
        })
        self.assertEqual(answer.status_code, 200, answer.text)
        self.assertEqual(answer.json()['intent'], 'GET_PRODUCTS')
        self.assertIn('Ống cầu thật: 80.000đ/ống, còn 4 ống', answer.json()['reply'])
        self.client.patch(f"/facility-products/{product['id']}/price", headers=self.owner_a, json={'price': 90000})
        self.client.patch(f"/facility-products/{product['id']}/inventory", headers=self.owner_a, json={
            'stock_quantity': 2, 'note': 'Đồng bộ tồn thực tế',
        })
        refreshed = self.client.post('/ai/assistant', headers=self.customer, json={
            'message': 'Số lượng còn và giá sản phẩm?', 'context_field_id': self.field_id,
        })
        self.assertIn('Ống cầu thật: 90.000đ/ống, còn 2 ống', refreshed.json()['reply'])

    def test_payment_qr_receipt_and_invoice_keep_court_service_breakdown(self):
        product = self.create_product(
            name='Nước điện giải', product_type='SELL', unit='chai',
            price=25000, sports=['Cầu lông'], stock_quantity=10, track_inventory=True,
        )
        created = self.client.post('/bookings', headers=self.customer, json={
            'field_id': self.field_id, 'time_slot_ids': [self.slot_id],
            'booking_date': (date.today() + timedelta(days=13)).isoformat(),
            'product_items': [{'product_id': product['id'], 'quantity': 2}],
        })
        self.assertEqual(created.status_code, 201, created.text)
        booking = created.json()
        self.assertEqual((booking['court_amount'], booking['service_amount'], booking['total_amount']), (200000, 50000, 250000))
        self.assertEqual(booking['deposit_amount'], 60000)

        intent = self.client.post('/payments/bank-intents', headers=self.customer, json={
            'booking_id': booking['id'], 'payment_type': 'deposit',
        })
        self.assertEqual(intent.status_code, 201, intent.text)
        self.assertEqual(intent.json()['amount'], 60000)
        self.assertIn('amount=60000', intent.json()['qr_url'])
        paid_deposit = self.client.post(f"/payments/{intent.json()['id']}/demo-confirm", headers=self.customer)
        self.assertEqual(paid_deposit.status_code, 200, paid_deposit.text)
        receipt = self.client.get(f"/payments/{intent.json()['id']}/deposit-receipt", headers=self.customer)
        self.assertEqual(receipt.status_code, 200, receipt.text)
        self.assertEqual((receipt.json()['court_amount'], receipt.json()['service_amount']), (200000, 50000))
        self.assertEqual(receipt.json()['remaining_amount'], 190000)
        self.assertEqual(receipt.json()['product_items'][0]['unit_price'], 25000)

        confirmed = self.client.patch(f"/bookings/{booking['id']}/confirm", headers=self.owner_a, json={})
        self.assertEqual(confirmed.status_code, 200, confirmed.text)
        remaining = self.client.post('/payments/bank-intents', headers=self.customer, json={
            'booking_id': booking['id'], 'payment_type': 'remaining',
        })
        self.assertEqual(remaining.status_code, 201, remaining.text)
        self.assertEqual(remaining.json()['amount'], 190000)
        settled = self.client.post(f"/payments/{remaining.json()['id']}/demo-confirm", headers=self.customer)
        self.assertEqual(settled.status_code, 200, settled.text)

        self.client.patch(f"/facility-products/{product['id']}/price", headers=self.owner_a, json={'price': 99000})
        with self.Session() as db:
            stored = db.get(Booking, booking['id'])
            stored.booking_date = date.today() - timedelta(days=1)
            db.commit()
        started = self.client.patch(f"/bookings/{booking['id']}/start", headers=self.owner_a, json={})
        self.assertEqual(started.status_code, 200, started.text)
        completed = self.client.patch(f"/bookings/{booking['id']}/complete", headers=self.owner_a, json={})
        self.assertEqual(completed.status_code, 200, completed.text)
        invoice = self.client.get(f"/bookings/{booking['id']}/invoice", headers=self.customer)
        self.assertEqual(invoice.status_code, 200, invoice.text)
        data = invoice.json()
        self.assertEqual((data['court_amount'], data['service_amount'], data['total_amount']), (200000, 50000, 250000))
        self.assertEqual(data['deposit_amount'], 60000)
        self.assertEqual(data['remaining_payment_amount'], 190000)
        self.assertEqual(data['product_items'][0]['unit_price'], 25000)

    def test_inventory_migration_upgrades_prompt_one_tables(self):
        engine = create_engine('sqlite://', poolclass=StaticPool)
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE facility_products (id INTEGER PRIMARY KEY, product_type VARCHAR(20) NOT NULL)"))
            connection.execute(text("CREATE TABLE booking_product_items (id INTEGER PRIMARY KEY)"))
            connection.execute(text("CREATE TABLE invoices (id INTEGER PRIMARY KEY, total_amount NUMERIC(12,2) NOT NULL)"))
            connection.execute(text("INSERT INTO facility_products (id, product_type) VALUES (1, 'SERVICE')"))
        migrate_product_inventory_schema(engine)
        product_columns = {item['name'] for item in inspect(engine).get_columns('facility_products')}
        booking_item_columns = {item['name'] for item in inspect(engine).get_columns('booking_product_items')}
        invoice_columns = {item['name'] for item in inspect(engine).get_columns('invoices')}
        self.assertTrue({'stock_quantity', 'reserved_quantity', 'track_inventory'} <= product_columns)
        self.assertTrue({'inventory_status', 'source', 'added_by'} <= booking_item_columns)
        self.assertTrue({'court_amount', 'service_amount'} <= invoice_columns)
        with engine.connect() as connection:
            row = connection.execute(text('SELECT stock_quantity, reserved_quantity, track_inventory FROM facility_products WHERE id=1')).one()
            self.assertEqual(tuple(row), (0, 0, 0))
        engine.dispose()


class ProductBookingConcurrencyTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        path = Path(self.temp.name) / 'product-concurrency.db'
        self.engine = create_engine(f'sqlite:///{path}', connect_args={'check_same_thread': False, 'timeout': 15})
        self.Session = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        Base.metadata.create_all(self.engine)
        with self.Session() as db:
            owner = User(full_name='Owner race', email='product-race-owner@test.local', hashed_password=get_password_hash('Owner@123'), role='OWNER')
            customers = [
                User(full_name='Customer A', email='product-race-a@test.local', hashed_password=get_password_hash('Customer@123'), role='CUSTOMER'),
                User(full_name='Customer B', email='product-race-b@test.local', hashed_password=get_password_hash('Customer@123'), role='CUSTOMER'),
            ]
            db.add_all([owner, *customers]); db.flush()
            facility = Facility(owner_id=owner.id, name='Cơ sở race', location='Hà Nội', sports=['Cầu lông'])
            db.add(facility); db.flush()
            fields = [
                Field(owner_id=owner.id, facility_id=facility.id, name=f'Sân {name}', sport_type='Cầu lông', location='Hà Nội', capacity=4, base_price=200000, amenities=[])
                for name in ('A', 'B')
            ]
            db.add_all(fields); db.flush()
            slots = [TimeSlot(field_id=field.id, name='Ca sáng', start_time=time(8), end_time=time(9), price=200000) for field in fields]
            db.add_all(slots); db.flush()
            product = FacilityProduct(
                facility_id=facility.id, name='Sản phẩm cuối', product_type='SELL', price=10000,
                unit='cái', status='ACTIVE', stock_quantity=1, reserved_quantity=0, track_inventory=True,
            )
            db.add(product); db.flush()
            from app.models.product import ProductSport
            db.add(ProductSport(product_id=product.id, sport_name='Cầu lông'))
            db.commit()
            self.field_ids = [field.id for field in fields]
            self.slot_ids = [slot.id for slot in slots]
            self.product_id = product.id
        def override_db():
            with self.Session() as db:
                yield db
        app.dependency_overrides[get_db] = override_db
        self.clients = [TestClient(app), TestClient(app)]
        self.headers = []
        for client, email in zip(self.clients, ['product-race-a@test.local', 'product-race-b@test.local']):
            token = client.post('/auth/login', json={'email': email, 'password': 'Customer@123'}).json()['access_token']
            self.headers.append({'Authorization': f'Bearer {token}'})

    def tearDown(self):
        for client in self.clients:
            client.close()
        app.dependency_overrides.clear(); self.engine.dispose(); self.temp.cleanup()

    def test_two_customers_cannot_reserve_the_last_product(self):
        booking_date = (date.today() + timedelta(days=20)).isoformat()
        def create(index):
            return self.clients[index].post('/bookings', headers=self.headers[index], json={
                'field_id': self.field_ids[index], 'time_slot_ids': [self.slot_ids[index]],
                'booking_date': booking_date,
                'product_items': [{'product_id': self.product_id, 'quantity': 1}],
            })
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(create, [0, 1]))
        self.assertEqual(sorted(response.status_code for response in responses), [201, 409])
        with self.Session() as db:
            product = db.get(FacilityProduct, self.product_id)
            self.assertEqual((product.stock_quantity, product.reserved_quantity), (1, 1))
            self.assertEqual(db.query(BookingProductItem).count(), 1)


if __name__ == '__main__':
    unittest.main()
