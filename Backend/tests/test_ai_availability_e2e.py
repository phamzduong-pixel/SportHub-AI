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
            
            maintenance = FieldMaintenance(field_id=1, starts_at=datetime.combine(date.today(), time(0,0), tzinfo=tz), ends_at=datetime.combine(date.today() + timedelta(days=30), time(23,59), tzinfo=tz))
            
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

    def test_newly_created_approved_facility_with_slots_is_suggested(self):
        from app.models.facility import Facility
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        with patch('app.repositories.booking_repository.BookingRepository.availability') as mock_avail:
            mock_facility = Facility(id=10, name='Cơ Sở Mới Hoàng Gia', location='Số 10 Duy Tân, Cầu Giấy, Hà Nội', city='Hà Nội', district='Cầu Giấy', status='APPROVED', is_active=True)
            mock_field = Field(id=50, name='Sân Cầu Lông VIP', sport_type='cầu lông', capacity=4, base_price=80000, location='Số 10 Duy Tân, Cầu Giấy, Hà Nội', facility_id=10, facility=mock_facility)
            mock_slot = TimeSlot(id=501, field_id=50, name='Ca tối 18h-19h30', start_time=time(18, 0), end_time=time(19, 30), price=80000, is_active=True, created_at=datetime.now(), updated_at=datetime.now())
            mock_avail.return_value = ([mock_field], [mock_slot], [], [], [])

            response = self.client.post('/ai/assistant', json={'message': f'Tìm sân cầu lông ngày {tomorrow} ở Cầu Giấy'})
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data['status'], 'OK')
            self.assertEqual(len(data['suggestions']), 1)
            self.assertEqual(data['suggestions'][0]['field_id'], 50)
            self.assertEqual(data['suggestions'][0]['time_slot_id'], 501)

    def test_nearest_alternative_slots_suggested_when_time_differs(self):
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        with patch('app.repositories.booking_repository.BookingRepository.availability') as mock_avail:
            mock_field = Field(id=1, name='Sân 1', sport_type='bóng đá', capacity=10, base_price=300000, location='Hà Nội', facility_id=1)
            # Slot is 18:00 - 19:30, but user asks for 14:00
            mock_slot = TimeSlot(id=101, field_id=1, name='Ca tối', start_time=time(18, 0), end_time=time(19, 30), price=300000, is_active=True, created_at=datetime.now(), updated_at=datetime.now())
            
            def avail_side_effect(booking_date, **kwargs):
                return ([mock_field], [mock_slot], [], [], [])

            mock_avail.side_effect = avail_side_effect

            response = self.client.post('/ai/assistant', json={'message': f'Tìm sân bóng đá lúc 14h ngày {tomorrow}'})
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data['status'], 'OK')
            self.assertGreaterEqual(len(data['suggestions']), 1)
            self.assertEqual(data['suggestions'][0]['start_time'], '18:00')
    def test_court_context_auto_resolves_sport_and_date_availability(self):
        target_date = (date.today() + timedelta(days=5)).isoformat()
        with patch('app.repositories.ai_repository.AIRepository.field_context') as mock_field_ctx, \
             patch('app.repositories.booking_repository.BookingRepository.availability') as mock_avail:
            mock_field = Field(id=7, name='Sân 7', sport_type='Bóng đá 7 người', capacity=14, base_price=300000, location='Cầu Giấy, Hà Nội', facility_id=1)
            mock_slot1 = TimeSlot(id=701, field_id=7, name='Ca 1', start_time=time(8, 0), end_time=time(9, 0), price=300000, is_active=True, created_at=datetime.now(), updated_at=datetime.now())
            mock_slot2 = TimeSlot(id=702, field_id=7, name='Ca 2', start_time=time(9, 0), end_time=time(10, 0), price=300000, is_active=True, created_at=datetime.now(), updated_at=datetime.now())
            mock_field_ctx.return_value = mock_field
            mock_avail.return_value = ([mock_field], [mock_slot1, mock_slot2], [], [], [])

            # User is on Sân 7 (context_field_id=7) and asks "Sân này còn khung giờ nào trống..."
            response = self.client.post('/ai/assistant', json={
                'message': f'Sân này còn khung giờ nào trống vào ngày {target_date}?',
                'context_field_id': 7,
            })
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data['status'], 'OK')
            self.assertEqual(len(data['suggestions']), 2)
            self.assertEqual(data['suggestions'][0]['field_id'], 7)
            self.assertEqual(data['suggestions'][0]['start_time'], '08:00')
            self.assertEqual(data['suggestions'][1]['start_time'], '09:00')

    def test_multi_turn_date_then_sport_then_other_courts_follow_up(self):
        target_date = (date.today() + timedelta(days=5)).isoformat()
        with patch('app.repositories.booking_repository.BookingRepository.availability') as mock_avail:
            mock_field1 = Field(id=7, name='Sân 7', sport_type='Bóng đá 7 người', capacity=14, base_price=300000, location='Cầu Giấy, Hà Nội', facility_id=1)
            mock_slot1 = TimeSlot(id=701, field_id=7, name='Ca 1', start_time=time(8, 0), end_time=time(9, 0), price=300000, is_active=True, created_at=datetime.now(), updated_at=datetime.now())
            mock_slot2 = TimeSlot(id=702, field_id=7, name='Ca 2', start_time=time(9, 0), end_time=time(10, 0), price=300000, is_active=True, created_at=datetime.now(), updated_at=datetime.now())

            mock_field2 = Field(id=8, name='Sân 8 Hoàng Gia', sport_type='Bóng đá mini', capacity=10, base_price=280000, location='Cầu Giấy, Hà Nội', facility_id=1)
            mock_slot3 = TimeSlot(id=801, field_id=8, name='Ca sáng Sân 8', start_time=time(8, 0), end_time=time(9, 30), price=280000, is_active=True, created_at=datetime.now(), updated_at=datetime.now())

            def avail_side_effect(field_id=None, **kwargs):
                if field_id == 7:
                    return ([mock_field1], [mock_slot1, mock_slot2], [], [], [])
                return ([mock_field1, mock_field2], [mock_slot1, mock_slot2, mock_slot3], [], [], [])

            mock_avail.side_effect = avail_side_effect

            # Turn 1: No context_field_id, asking for date
            res1 = self.client.post('/ai/assistant', json={
                'message': f'Sân này còn khung giờ nào trống vào ngày {target_date}?',
            })
            self.assertEqual(res1.status_code, 200)
            data1 = res1.json()
            self.assertEqual(data1['status'], 'NEED_MORE_DATA')
            self.assertIn('môn thể thao', data1['reply'])
            self.assertEqual(data1['understood']['booking_date'], target_date)

            # Turn 2: User answers "môn bóng đá"
            res2 = self.client.post('/ai/assistant', json={
                'message': 'môn bóng đá',
                'context': data1['understood'],
            })
            self.assertEqual(res2.status_code, 200)
            data2 = res2.json()
            self.assertEqual(data2['status'], 'OK')
            self.assertGreaterEqual(len(data2['suggestions']), 1)
            self.assertEqual(data2['understood']['sport_type'], 'bóng đá')
            self.assertEqual(data2['understood']['booking_date'], target_date)

            # Turn 3: User asks "vậy còn sân nào không?"
            res3 = self.client.post('/ai/assistant', json={
                'message': 'vậy còn sân nào không?',
                'context': data2['understood'],
            })
            self.assertEqual(res3.status_code, 200)
            data3 = res3.json()
            self.assertEqual(data3['status'], 'OK')
            self.assertGreaterEqual(len(data3['suggestions']), 2)


if __name__ == '__main__':
    unittest.main()
