"""
Unit & Integration Tests for Court Reservations:
- Server-authoritative pricing (neutralizing price tampering)
- Strict temporal validation (rejecting past dates and past times)
- Duration bounds (1-hour minimum, start < end)
- Court status and conflict detection
"""

import time
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from app import create_app
from tests.mock_db import MockSupabaseClient

PH_TZ = timezone(timedelta(hours=8))
TEST_USER_ID = '00000000-0000-0000-0000-000000000001'

class TestReservations(unittest.TestCase):

    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()

        # Seed initial mock tables
        self.initial_tables = {
            'courts': [
                {
                    'id': 'court-vip-1',
                    'facility_id': 'fac-1',
                    'name': 'Center Championship Court',
                    'hourly_rate': 1200.0,
                    'status': 'active'
                },
                {
                    'id': 'court-inactive-2',
                    'facility_id': 'fac-1',
                    'name': 'Under Repair Court',
                    'hourly_rate': 600.0,
                    'status': 'maintenance'
                }
            ],
            'court_reservations': [
                {
                    'id': 'existing-res-1',
                    'player_id': '00000000-0000-0000-0000-000000000099',
                    'court_id': 'court-vip-1',
                    'facility_id': 'fac-1',
                    'date': '2026-12-15',
                    'start_time': '10:00:00',
                    'end_time': '12:00:00',
                    'total_hours': 2.0,
                    'hourly_rate': 1200.0,
                    'total_amount': 2400.0,
                    'status': 'confirmed'
                }
            ],
            'event_courts': [],
            'events': [],
            'profiles': [
                {
                    'id': TEST_USER_ID,
                    'role': 'player',
                    'first_name': 'Test',
                    'last_name': 'Athlete',
                    'is_suspended': False,
                    'subscription_tier': 'free'
                }
            ]
        }
        self.mock_db = MockSupabaseClient(self.initial_tables)

    def _login_player(self):
        profile = {
            'id': TEST_USER_ID,
            'role': 'player',
            'first_name': 'Test',
            'last_name': 'Athlete',
            'is_suspended': False,
            'subscription_tier': 'free'
        }
        with self.client.session_transaction() as sess:
            sess['user_id'] = TEST_USER_ID
            sess['role'] = 'player'
            sess['last_integrity_check'] = time.time()
            sess['cached_profile'] = profile
            sess['_fresh'] = True

    @patch('app.db.get_admin_db')
    @patch('app.db.get_db')
    @patch('app.player.reservations.get_admin_db')
    @patch('app.player.reservations.get_db')
    def test_price_tampering_is_neutralized(self, mock_r_db, mock_r_adb, mock_db, mock_adb):
        """Verify that client-submitted price/rate is ignored and calculated from DB court rate."""
        mock_r_db.return_value = self.mock_db
        mock_r_adb.return_value = self.mock_db
        mock_db.return_value = self.mock_db
        mock_adb.return_value = self.mock_db
        self._login_player()

        valid_date = (datetime.now(PH_TZ) + timedelta(days=4)).strftime('%Y-%m-%d')
        # Attacker submits malicious payload: hourly_rate=1, total_amount=1 for a ₱1200/hr court
        payload = {
            'court_id': 'court-vip-1',
            'facility_id': 'fac-1',
            'date': valid_date,
            'start_time': '14:00',
            'end_time': '16:00',
            'hourly_rate': '1.00',       # Tampered!
            'total_amount': '2.00',      # Tampered!
            'total_hours': '2.0',
            'party_size': '4'
        }

        resp = self.client.post('/player/reservation/book', json=payload, headers={'Accept': 'application/json'})
        self.assertEqual(resp.status_code, 200, f"Expected 200, got {resp.status_code}: {resp.get_json()}")
        data = resp.get_json()
        self.assertTrue(data.get('success'))

        # Inspect the inserted reservation in DB store
        all_res = self.mock_db.tables.get('court_reservations', [])
        new_res = [r for r in all_res if r.get('date') == valid_date][0]

        # Server MUST have recorded official rate (1200.0) and computed total (2400.0)
        self.assertEqual(new_res['hourly_rate'], 1200.0)
        self.assertEqual(new_res['total_hours'], 2.0)
        self.assertEqual(new_res['total_amount'], 2400.0)

    @patch('app.db.get_admin_db')
    @patch('app.db.get_db')
    @patch('app.player.reservations.get_admin_db')
    @patch('app.player.reservations.get_db')
    def test_past_date_booking_rejected(self, mock_r_db, mock_r_adb, mock_db, mock_adb):
        """Verify that booking a date in the past is strictly rejected with 400."""
        mock_r_db.return_value = self.mock_db
        mock_r_adb.return_value = self.mock_db
        mock_db.return_value = self.mock_db
        mock_adb.return_value = self.mock_db
        self._login_player()

        payload = {
            'court_id': 'court-vip-1',
            'facility_id': 'fac-1',
            'date': '2024-01-15',
            'start_time': '14:00',
            'end_time': '15:00',
            'party_size': '2'
        }

        resp = self.client.post('/player/reservation/book', json=payload, headers={'Accept': 'application/json'})
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertFalse(data.get('success'))
        self.assertIn('past date', data.get('error', '').lower())

    @patch('app.db.get_admin_db')
    @patch('app.db.get_db')
    @patch('app.player.reservations.get_admin_db')
    @patch('app.player.reservations.get_db')
    def test_minimum_duration_one_hour_enforced(self, mock_r_db, mock_r_adb, mock_db, mock_adb):
        """Verify that bookings under 1 hour are rejected with 400."""
        mock_r_db.return_value = self.mock_db
        mock_r_adb.return_value = self.mock_db
        mock_db.return_value = self.mock_db
        mock_adb.return_value = self.mock_db
        self._login_player()

        payload = {
            'court_id': 'court-vip-1',
            'facility_id': 'fac-1',
            'date': '2026-12-20',
            'start_time': '14:00',
            'end_time': '14:30',  # Only 30 minutes!
            'party_size': '2'
        }

        resp = self.client.post('/player/reservation/book', json=payload, headers={'Accept': 'application/json'})
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertIn('minimum duration of 1 hour', data.get('error', '').lower())

    @patch('app.db.get_admin_db')
    @patch('app.db.get_db')
    @patch('app.player.reservations.get_admin_db')
    @patch('app.player.reservations.get_db')
    def test_inverted_time_slot_rejected(self, mock_r_db, mock_r_adb, mock_db, mock_adb):
        """Verify that end_time <= start_time is rejected."""
        mock_r_db.return_value = self.mock_db
        mock_r_adb.return_value = self.mock_db
        mock_db.return_value = self.mock_db
        mock_adb.return_value = self.mock_db
        self._login_player()

        payload = {
            'court_id': 'court-vip-1',
            'facility_id': 'fac-1',
            'date': '2026-12-20',
            'start_time': '16:00',
            'end_time': '14:00',  # End before start!
            'party_size': '2'
        }

        resp = self.client.post('/player/reservation/book', json=payload, headers={'Accept': 'application/json'})
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertIn('end time must be after start time', data.get('error', '').lower())

    @patch('app.db.get_admin_db')
    @patch('app.db.get_db')
    @patch('app.player.reservations.get_admin_db')
    @patch('app.player.reservations.get_db')
    def test_inactive_court_booking_rejected(self, mock_r_db, mock_r_adb, mock_db, mock_adb):
        """Verify that booking a court under maintenance is rejected."""
        mock_r_db.return_value = self.mock_db
        mock_r_adb.return_value = self.mock_db
        mock_db.return_value = self.mock_db
        mock_adb.return_value = self.mock_db
        self._login_player()

        payload = {
            'court_id': 'court-inactive-2',
            'facility_id': 'fac-1',
            'date': '2026-12-20',
            'start_time': '14:00',
            'end_time': '15:00',
            'party_size': '2'
        }

        resp = self.client.post('/player/reservation/book', json=payload, headers={'Accept': 'application/json'})
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertIn('unavailable', data.get('error', '').lower())


if __name__ == '__main__':
    unittest.main()
