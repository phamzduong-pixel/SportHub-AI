import unittest
from datetime import date, time, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.security import create_access_token
from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models.field import Booking, Field
from app.models.time_slot import TimeSlot
from app.models.user import User

class OwnerIsolationTests(unittest.TestCase):
    def setUp(self):
        self.engine=create_engine('sqlite://', connect_args={'check_same_thread':False}, poolclass=StaticPool); self.Session=sessionmaker(bind=self.engine); Base.metadata.create_all(self.engine)
        with self.Session() as db:
            a=User(full_name='Owner A',email='a@owner.local',hashed_password='unused',role='OWNER'); b=User(full_name='Owner B',email='b@owner.local',hashed_password='unused',role='OWNER'); c=User(full_name='Customer',email='c@local',hashed_password='unused',role='CUSTOMER'); db.add_all([a,b,c]); db.flush()
            fa=Field(owner_id=a.id,name='Court A',sport_type='football',location='A',capacity=10,base_price=100,amenities=[]); fb=Field(owner_id=b.id,name='Court B',sport_type='football',location='B',capacity=10,base_price=100,amenities=[]); db.add_all([fa,fb]); db.flush(); slot=TimeSlot(field_id=fb.id,name='Slot',start_time=time(8),end_time=time(9),price=100); db.add(slot); db.flush(); db.add(Booking(booking_code='B-BOOKING',customer_id=c.id,field_id=fb.id,time_slot_id=slot.id,booking_date=date.today()+timedelta(1),start_time_snapshot=time(8),end_time_snapshot=time(9),price_snapshot=100,total_amount=100,status='confirmed')); db.commit(); self.a=a.id; self.b=b.id; self.fb=fb.id
        def override_db():
            with self.Session() as db: yield db
        app.dependency_overrides[get_db]=override_db; self.client=TestClient(app)
    def tearDown(self): self.client.close(); app.dependency_overrides.clear(); Base.metadata.drop_all(self.engine)
    def headers(self,user_id): return {'Authorization':f"Bearer {create_access_token({'sub':str(user_id),'role':'OWNER'})}"}
    def test_owner_a_cannot_access_owner_b_data(self):
        a=self.headers(self.a); b=self.headers(self.b); self.assertEqual([x['name'] for x in self.client.get('/fields?page_size=100',headers=a).json()['items']],['Court A']); self.assertEqual(self.client.get(f'/fields/{self.fb}',headers=a).status_code,404); self.assertEqual(self.client.get('/bookings',headers=a).json()['total'],0); self.assertEqual(self.client.get('/bookings',headers=b).json()['total'],1)

if __name__=='__main__': unittest.main()
