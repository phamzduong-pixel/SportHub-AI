import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.security import get_password_hash
from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models.user import User, UserRole

JPEG = b'\xff\xd8\xff\xe0avatar-image\xff\xd9'


class AvatarTests(unittest.TestCase):
    def setUp(self):
        self.upload_dir = tempfile.TemporaryDirectory()
        self.old_dir, self.old_limit = settings.AVATAR_DIR, settings.AVATAR_MAX_BYTES
        settings.AVATAR_DIR = Path(self.upload_dir.name).resolve(); settings.AVATAR_MAX_BYTES = 5 * 1024 * 1024
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        self.Session = sessionmaker(bind=self.engine); Base.metadata.create_all(self.engine)
        with self.Session() as db:
            db.add_all([
                User(full_name='Avatar A', email='avatar.a@test.local', hashed_password=get_password_hash('Password@123'), role=UserRole.CUSTOMER.value),
                User(full_name='Avatar B', email='avatar.b@test.local', hashed_password=get_password_hash('Password@123'), role=UserRole.CUSTOMER.value),
            ]); db.commit()
        def override_db():
            with self.Session() as db: yield db
        app.dependency_overrides[get_db] = override_db; self.client = TestClient(app)

    def tearDown(self):
        self.client.close(); app.dependency_overrides.clear(); Base.metadata.drop_all(self.engine)
        settings.AVATAR_DIR, settings.AVATAR_MAX_BYTES = self.old_dir, self.old_limit
        self.upload_dir.cleanup()

    def headers(self, email):
        response = self.client.post('/auth/login', json={'email': email, 'password': 'Password@123'})
        self.assertEqual(response.status_code, 200, response.text)
        return {'Authorization': f"Bearer {response.json()['access_token']}"}

    def test_valid_upload_is_saved_synced_and_survives_refresh(self):
        headers = self.headers('avatar.a@test.local')
        uploaded = self.client.post('/auth/profile/avatar', headers=headers, files={'avatar': ('avatar.jpg', JPEG, 'image/jpeg')})
        self.assertEqual(uploaded.status_code, 200, uploaded.text)
        avatar_url = uploaded.json()['avatar_url']; self.assertTrue(avatar_url.startswith('/api/auth/avatars/'))
        self.assertEqual(self.client.get('/auth/me', headers=headers).json()['avatar_url'], avatar_url)
        public_image = self.client.get(avatar_url.removeprefix('/api'))
        self.assertEqual(public_image.status_code, 200); self.assertEqual(public_image.content, JPEG)
        with self.Session() as db:
            self.assertEqual(db.scalar(select(User).where(User.email == 'avatar.a@test.local')).avatar_url, avatar_url)

    def test_invalid_mime_and_oversize_keep_old_avatar(self):
        headers = self.headers('avatar.a@test.local')
        old_url = self.client.post('/auth/profile/avatar', headers=headers, files={'avatar': ('old.jpg', JPEG, 'image/jpeg')}).json()['avatar_url']
        invalid = self.client.post('/auth/profile/avatar', headers=headers, files={'avatar': ('fake.png', b'not-an-image', 'image/png')})
        self.assertEqual(invalid.status_code, 415)
        settings.AVATAR_MAX_BYTES = 8
        oversized = self.client.post('/auth/profile/avatar', headers=headers, files={'avatar': ('large.jpg', JPEG, 'image/jpeg')})
        self.assertEqual(oversized.status_code, 413)
        self.assertEqual(self.client.get('/auth/me', headers=headers).json()['avatar_url'], old_url)

    def test_storage_failure_keeps_old_avatar(self):
        headers = self.headers('avatar.a@test.local')
        old_url = self.client.post('/auth/profile/avatar', headers=headers, files={'avatar': ('old.jpg', JPEG, 'image/jpeg')}).json()['avatar_url']
        with patch('app.api.routes.auth.store_avatar', new=AsyncMock(side_effect=HTTPException(status_code=500, detail='storage failed'))):
            failed = self.client.post('/auth/profile/avatar', headers=headers, files={'avatar': ('new.jpg', JPEG, 'image/jpeg')})
        self.assertEqual(failed.status_code, 500)
        self.assertEqual(self.client.get('/auth/me', headers=headers).json()['avatar_url'], old_url)

    def test_upload_only_changes_authenticated_user(self):
        a = self.headers('avatar.a@test.local'); b = self.headers('avatar.b@test.local')
        first = self.client.post('/auth/profile/avatar', headers=a, files={'avatar': ('a.jpg', JPEG, 'image/jpeg')}).json()['avatar_url']
        second = self.client.post('/auth/profile/avatar', headers=b, files={'avatar': ('b.jpg', JPEG, 'image/jpeg')}).json()['avatar_url']
        self.assertNotEqual(first, second)
        self.assertEqual(self.client.get('/auth/me', headers=a).json()['avatar_url'], first)
        self.assertEqual(self.client.get('/auth/me', headers=b).json()['avatar_url'], second)

    def test_profile_update_does_not_reset_avatar(self):
        headers = self.headers('avatar.a@test.local')
        avatar_url = self.client.post('/auth/profile/avatar', headers=headers, files={'avatar': ('avatar.jpg', JPEG, 'image/jpeg')}).json()['avatar_url']
        updated = self.client.put('/auth/profile', headers=headers, json={'full_name': 'Avatar Updated'})
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()['avatar_url'], avatar_url)


if __name__ == '__main__':
    unittest.main()
