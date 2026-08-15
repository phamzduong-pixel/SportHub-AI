import asyncio
import unittest
from contextlib import ExitStack
from unittest.mock import patch

from app.main import app, lifespan


class LifespanCleanupTests(unittest.TestCase):
    def test_lifespan_disposes_database_engine_on_shutdown(self):
        no_op = lambda *args, **kwargs: None
        migration_names = [
            'migrate_empty_legacy_booking_schema',
            'migrate_field_recommendation_columns',
            'migrate_user_profile_columns',
            'migrate_ownership_columns',
            'migrate_system_roles',
            'migrate_deposit_payment_schema',
            'migrate_professional_booking_schema',
            'migrate_partner_application_schema',
            'migrate_facility_approval_schema',
            'migrate_refund_workflow_schema',
            'migrate_cancelled_booking_balances',
        ]

        async def run_lifespan():
            with ExitStack() as stack:
                for name in migration_names:
                    stack.enter_context(patch(f'app.main.{name}', side_effect=no_op))
                stack.enter_context(patch('app.main.Base.metadata.create_all', side_effect=no_op))
                stack.enter_context(patch('app.main.seed_demo_db', side_effect=no_op))
                dispose = stack.enter_context(patch('app.main.engine.dispose'))
                async with lifespan(app):
                    dispose.assert_not_called()
                dispose.assert_called_once_with()

        asyncio.run(run_lifespan())


if __name__ == '__main__':
    unittest.main()
