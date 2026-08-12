import unittest
from datetime import time
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.config import settings
from app.core.security import get_password_hash
from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models.facility import Facility
from app.models.field import Field
from app.models.time_slot import TimeSlot
from app.models.user import User, UserRole

class SystemAdminTests(unittest.TestCase):
    def setUp(self):
        self.engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool); self.Session=sessionmaker(bind=self.engine); Base.metadata.create_all(self.engine)
        with self.Session() as db:
            admin=User(full_name='Admin',email='admin@test.local',hashed_password=get_password_hash('Admin@123456'),role=UserRole.SYSTEM_ADMIN.value); owner=User(full_name='Owner',email='owner@test.local',hashed_password=get_password_hash('Owner@123456'),role=UserRole.OWNER.value); customer=User(full_name='Customer',email='customer@test.local',hashed_password=get_password_hash('Customer@123'),role=UserRole.CUSTOMER.value); db.add_all([admin,owner,customer]); db.flush(); facility=Facility(owner_id=owner.id,name='Facility',location='Hà Nội',amenities=[],image_urls=[]); db.add(facility); db.flush(); field=Field(owner_id=owner.id,facility_id=facility.id,name='Court',sport_type='cầu lông',location='Hà Nội',capacity=4,base_price=100000,amenities=[]); db.add(field); db.flush(); db.add(TimeSlot(field_id=field.id,name='19h',start_time=time(19),end_time=time(20),price=100000)); db.commit(); self.ids={'admin':admin.id,'owner':owner.id,'customer':customer.id,'facility':facility.id,'field':field.id}
        def override_db():
            with self.Session() as db: yield db
        app.dependency_overrides[get_db]=override_db; self.client=TestClient(app)
    def tearDown(self): self.client.close(); app.dependency_overrides.clear(); Base.metadata.drop_all(self.engine)
    def login(self,email,password): response=self.client.post('/auth/login',json={'email':email,'password':password}); self.assertEqual(response.status_code,200,response.text); return response.json()
    def headers(self,email,password): return {'Authorization':f"Bearer {self.login(email,password)['access_token']}"}
    def test_only_three_roles_and_public_registration_customer(self):
        self.assertEqual({role.value for role in UserRole},{'CUSTOMER','OWNER','SYSTEM_ADMIN'}); payload={'full_name':'New User','email':'new@test.local','phone':'0905555555','password':'Customer@123'}; created=self.client.post('/auth/register',json=payload); self.assertEqual(created.json()['role'],'CUSTOMER'); self.assertEqual(self.client.post('/auth/register',json={**payload,'email':'x@test.local','role':'OWNER'}).status_code,422); self.assertEqual(self.client.post('/auth/register',json={**payload,'email':'y@test.local','role':'SYSTEM_ADMIN'}).status_code,422)
    def test_owner_application_keeps_customer_until_admin_approval(self):
        customer=self.headers('customer@test.local','Customer@123'); requested=self.client.post('/auth/request-owner',headers=customer,json={'representative':{'name':'Customer','phone':'0901234567','email':'customer@test.local'},'venue':{'name':'New Venue','address':'1 Test Street','description':'Muon tro thanh chu san'},'legal_confirmed':True}); self.assertEqual(requested.status_code,200,requested.text); self.assertEqual(self.client.get('/auth/me',headers=customer).json()['role'],'CUSTOMER'); admin=self.headers('admin@test.local','Admin@123456'); applications=self.client.get('/admin/owner-applications',headers=admin).json(); approved=self.client.patch(f"/admin/owner-applications/{applications[0]['id']}",headers=admin,json={'approved':True,'rejection_reason':None}); self.assertEqual(approved.status_code,200); self.assertEqual(self.login('customer@test.local','Customer@123')['user']['role'],'OWNER')
    def test_jwt_and_admin_authorization(self):
        session=self.login('admin@test.local','Admin@123456'); claims=jwt.decode(session['access_token'],settings.SECRET_KEY,algorithms=[settings.ALGORITHM]); self.assertEqual(claims['role'],'SYSTEM_ADMIN'); customer=self.headers('customer@test.local','Customer@123'); owner=self.headers('owner@test.local','Owner@123456'); admin={'Authorization':f"Bearer {session['access_token']}"}; self.assertEqual(self.client.get('/admin/summary',headers=customer).status_code,403); self.assertEqual(self.client.get('/admin/summary',headers=owner).status_code,403); self.assertEqual(self.client.get('/admin/summary',headers=admin).status_code,200); self.assertEqual(self.client.post('/fields',headers=admin,json={}).status_code,403)
    def test_locked_facility_removed_from_inventory(self):
        admin=self.headers('admin@test.local','Admin@123456'); self.assertEqual(self.client.get(f"/public/courts/{self.ids['field']}").status_code,200); self.client.patch(f"/admin/facilities/{self.ids['facility']}/status",headers=admin,json={'is_active':False}); self.assertEqual(self.client.get(f"/public/courts/{self.ids['field']}").status_code,404)
    def test_ai_platform_scope(self):
        admin=self.headers('admin@test.local','Admin@123456'); response=self.client.post('/ai/assistant',headers=admin,json={'message':'Có bao nhiêu OWNER đang hoạt động?'}); self.assertEqual(response.status_code,200); self.assertIn('1 OWNER',response.json()['reply'])

    def test_user_filters_lock_unlock_and_owner_metrics(self):
        admin=self.headers('admin@test.local','Admin@123456')
        locked=self.client.patch(f"/admin/users/{self.ids['customer']}/status",headers=admin,json={'is_active':False})
        self.assertEqual(locked.status_code,200); self.assertFalse(locked.json()['is_active'])
        self.assertEqual(self.client.post('/auth/login',json={'email':'customer@test.local','password':'Customer@123'}).status_code,403)
        reopened=self.client.patch(f"/admin/users/{self.ids['customer']}/status",headers=admin,json={'is_active':True})
        self.assertTrue(reopened.json()['is_active'])
        owners=self.client.get('/admin/owners',headers=admin)
        self.assertEqual(owners.status_code,200,owners.text); self.assertEqual(owners.json()['total'],1)
        self.assertEqual(owners.json()['items'][0]['facility_count'],1); self.assertEqual(owners.json()['items'][0]['field_count'],1)

    def test_customer_cannot_access_owner_apis(self):
        customer=self.headers('customer@test.local','Customer@123')
        self.assertEqual(self.client.get('/facilities',headers=customer).status_code,403)
        self.assertEqual(self.client.get('/management/customers',headers=customer).status_code,403)
        self.assertEqual(self.client.get('/dashboard/summary',headers=customer).status_code,403)
        self.assertEqual(self.client.get('/maintenance',headers=customer).status_code,403)

if __name__=='__main__': unittest.main()
