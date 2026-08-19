from datetime import date, timedelta, datetime, time
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.models.field import Field, Booking, BookingSlot
from app.models.time_slot import TimeSlot
from app.models.maintenance import FieldMaintenance

class AssistantRankingProvider:
    def generate_json(self, **kwargs):
        available = kwargs['system_data']['available_slots']
        return {'status': 'OK', 'recommendations': [
            {'court_id': item['court_id'], 'slot_id': item['slot_id'], 'reason': 'Phù hợp nhu cầu.'}
            for item in available[:3]
        ]}

class AIAvailabilityE2ETests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.provider_patch = patch('app.services.ai_feature_service.StructuredAIProvider', return_value=AssistantRankingProvider())
        cls.provider_patch.start()
        cls.client = TestClient(app)
        cls.context = cls.client.__enter__()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.client.__exit__(None, None, None)
        finally:
            cls.client.close()
            cls.provider_patch.stop()

    def test_no_slots_found_in_7_days(self):
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        with patch('app.repositories.booking_repository.BookingRepository.availability', return_value=([], [], [], [], [])):
            response = self.client.post('/ai/assistant', json={'message': f'Tìm sân tennis ngày {tomorrow}'})
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertIn('Không có khung giờ', payload['reply'])
            self.assertEqual(len(payload['suggestions']), 0)

    def test_follow_up_buoi_toi_thi_sao(self):
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        context = {
            'sport_type': 'tennis',
            'booking_date': tomorrow
        }
        with patch('app.repositories.booking_repository.BookingRepository.availability') as mock_avail:
            mock_field = Field(id=1, name='Sân 1', sport_type='tennis', capacity=4, base_price=100000, location='Hà Nội', facility_id=1)
            mock_slot_am = TimeSlot(id=101, field_id=1, name='Ca sáng', start_time=time(8,0), end_time=time(9,0), price=100000, is_active=True, created_at=datetime.now(), updated_at=datetime.now())
            mock_slot_pm = TimeSlot(id=102, field_id=1, name='Ca tối', start_time=time(19,0), end_time=time(20,0), price=120000, is_active=True, created_at=datetime.now(), updated_at=datetime.now())
            mock_avail.return_value = ([mock_field], [mock_slot_am, mock_slot_pm], [], [], [])
            
            response = self.client.post('/ai/assistant', json={'message': 'Buổi tối thì sao?', 'context': context})
            self.assertEqual(response.status_code, 200)
            suggestions = response.json()['suggestions']
            self.assertEqual(len(suggestions), 1)
            self.assertEqual(suggestions[0]['time_slot_id'], 102)

    def test_follow_up_ngay_nao_trong(self):
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        context = {
            'sport_type': 'tennis',
            'booking_date': tomorrow
        }
        with patch('app.repositories.booking_repository.BookingRepository.availability') as mock_avail:
            def side_effect(booking_date, **kwargs):
                if booking_date == date.today() + timedelta(days=1):
                    return ([], [], [], [], [])
                
                mock_field = Field(id=1, name='Sân 1', sport_type='tennis', capacity=4, base_price=100000, location='Hà Nội', facility_id=1)
                mock_slot = TimeSlot(id=101, field_id=1, name='Ca sáng', start_time=time(8,0), end_time=time(9,0), price=100000, is_active=True, created_at=datetime.now(), updated_at=datetime.now())
                return ([mock_field], [mock_slot], [], [], [])
            
            mock_avail.side_effect = side_effect
            
            response = self.client.post('/ai/assistant', json={'message': 'Vậy còn ngày nào trống?', 'context': context})
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertIn('Gần nhất tôi tìm thấy:', payload['reply'])
            self.assertGreaterEqual(len(payload['suggestions']), 1)
            self.assertEqual(payload['suggestions'][0]['booking_date'], (date.today() + timedelta(days=2)).isoformat())

    def test_maintenance_slot_is_not_suggested(self):
        from zoneinfo import ZoneInfo
        tz = ZoneInfo("Asia/Ho_Chi_Minh")
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        with patch('app.repositories.booking_repository.BookingRepository.availability') as mock_avail:
            mock_field = Field(id=1, name='Sân 1', sport_type='tennis', capacity=4, base_price=100000, location='Hà Nội', facility_id=1)
            mock_slot = TimeSlot(id=101, field_id=1, name='Ca sáng', start_time=time(8,0), end_time=time(9,0), price=100000, is_active=True, created_at=datetime.now(), updated_at=datetime.now())
            
            maintenance = FieldMaintenance(field_id=1, starts_at=datetime.combine(date.today() + timedelta(days=1), time(7,0), tzinfo=tz), ends_at=datetime.combine(date.today() + timedelta(days=1), time(10,0), tzinfo=tz))
            
            mock_avail.return_value = ([mock_field], [mock_slot], [], [], [maintenance])
            
            response = self.client.post('/ai/assistant', json={'message': f'Tìm sân tennis ngày {tomorrow}'})
            self.assertEqual(len(response.json()['suggestions']), 0)
            self.assertIn('Không có khung giờ', response.json()['reply'])

    def test_booked_multi_slot_is_not_suggested(self):
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        with patch('app.repositories.booking_repository.BookingRepository.availability') as mock_avail:
            mock_field = Field(id=1, name='Sân 1', sport_type='tennis', capacity=4, base_price=100000, location='Hà Nội', facility_id=1)
            mock_slot1 = TimeSlot(id=101, field_id=1, name='Ca 1', start_time=time(8,0), end_time=time(9,0), price=100000, is_active=True, created_at=datetime.now(), updated_at=datetime.now())
            mock_slot2 = TimeSlot(id=102, field_id=1, name='Ca 2', start_time=time(9,0), end_time=time(10,0), price=100000, is_active=True, created_at=datetime.now(), updated_at=datetime.now())
            
            booking = Booking(field_id=1, start_time_snapshot=time(8,0), end_time_snapshot=time(10,0), booking_slots=[
                BookingSlot(time_slot_id=101, start_time_snapshot=time(8,0), end_time_snapshot=time(9,0)),
                BookingSlot(time_slot_id=102, start_time_snapshot=time(9,0), end_time_snapshot=time(10,0))
            ])
            
            mock_avail.return_value = ([mock_field], [mock_slot1, mock_slot2], [booking], [], [])
            
            response = self.client.post('/ai/assistant', json={'message': f'Tìm sân tennis ngày {tomorrow}'})
            self.assertEqual(len(response.json()['suggestions']), 0)

if __name__ == '__main__':
    unittest.main()
