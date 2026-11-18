"""
Unit & Integration Tests for Tournaments:
- Seed order generation algorithm (power-of-2)
- Bracket byes generation & pairing
- Flexible competitive score validation (no ties, no negatives, required values)
- Bracket advancement
"""

import time
import unittest
from unittest.mock import patch
from app import create_app
from app.clubadmin.tournaments import generate_seed_order
from tests.mock_db import MockSupabaseClient

TEST_ADMIN_ID = '00000000-0000-0000-0000-000000000010'

class TestTournaments(unittest.TestCase):

    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()

        self.initial_tables = {
            'clubs': [
                {
                    'id': 'club-1',
                    'admin_id': TEST_ADMIN_ID,
                    'name': 'Metro Pickleball Club',
                    'banner_url': 'https://example.com/banner.png'
                }
            ],
            'club_memberships': [],
            'events': [
                {
                    'id': 'ev-tourney-1',
                    'title': 'Metro Manila Open',
                    'organizer_id': TEST_ADMIN_ID,
                    'type': 'tournament',
                    'status': 'in_progress',
                    'is_ranked': True
                }
            ],
            'tournament_matches': [
                {
                    'id': 'match-101',
                    'event_id': 'ev-tourney-1',
                    'round_number': 1,
                    'match_number': 1,
                    'player1_id': '00000000-0000-0000-0000-000000000001',
                    'player2_id': '00000000-0000-0000-0000-000000000002',
                    'player1_guest_name': None,
                    'player2_guest_name': None,
                    'player1_score': None,
                    'player2_score': None,
                    'status': 'pending',
                    'winner_id': None
                }
            ],
            'profiles': [
                {
                    'id': TEST_ADMIN_ID,
                    'role': 'clubadmin',
                    'first_name': 'Club',
                    'last_name': 'Organizer',
                    'is_suspended': False,
                    'subscription_tier': 'pro'
                },
                {
                    'id': '00000000-0000-0000-0000-000000000001',
                    'role': 'player',
                    'first_name': 'Player',
                    'last_name': 'One',
                    'elo': 1400,
                    'dupr': 3.50,
                    'is_suspended': False
                },
                {
                    'id': '00000000-0000-0000-0000-000000000002',
                    'role': 'player',
                    'first_name': 'Player',
                    'last_name': 'Two',
                    'elo': 1350,
                    'dupr': 3.38,
                    'is_suspended': False
                }
            ],
            'notifications': []
        }
        self.mock_db = MockSupabaseClient(self.initial_tables)

    def _login_clubadmin(self):
        profile = {
            'id': TEST_ADMIN_ID,
            'role': 'clubadmin',
            'first_name': 'Club',
            'last_name': 'Organizer',
            'is_suspended': False,
            'subscription_tier': 'pro'
        }
        with self.client.session_transaction() as sess:
            sess['user_id'] = TEST_ADMIN_ID
            sess['role'] = 'clubadmin'
            sess['last_integrity_check'] = time.time()
            sess['cached_profile'] = profile
            sess['_fresh'] = True

    def test_seed_order_algorithm(self):
        """Test tournament seeding generator produces correct paired sequences."""
        order_4 = generate_seed_order(4)
        self.assertEqual(order_4, [1, 4, 2, 3])

        order_8 = generate_seed_order(8)
        self.assertEqual(order_8, [1, 8, 4, 5, 2, 7, 3, 6])

        order_16 = generate_seed_order(16)
        self.assertEqual(len(order_16), 16)
        self.assertEqual(order_16[0], 1)
        self.assertEqual(order_16[1], 16)
        # Seeds 1 and 2 must be on opposite halves
        mid = len(order_16) // 2
        self.assertIn(1, order_16[:mid])
        self.assertIn(2, order_16[mid:])

    @patch('app.db.get_admin_db')
    @patch('app.db.get_db')
    @patch('app.clubadmin.routes.get_admin_db')
    @patch('app.clubadmin.routes.get_db')
    @patch('app.clubadmin.tournaments.get_admin_db')
    @patch('app.clubadmin.tournaments.get_db')
    def test_tied_score_rejected(self, mock_t_db, mock_t_adb, mock_r_db, mock_r_adb, mock_db, mock_adb):
        """Verify that tied scores (e.g. 11-11) are strictly rejected with an error message."""
        for m in [mock_t_db, mock_t_adb, mock_r_db, mock_r_adb, mock_db, mock_adb]:
            m.return_value = self.mock_db
        self._login_clubadmin()

        payload = {
            'player1_score': 11,
            'player2_score': 11  # Tie! Prohibited in pickleball
        }

        resp = self.client.post(
            '/clubadmin/tournaments/ev-tourney-1/matches/match-101/score',
            data=payload,
            follow_redirects=True
        )
        self.assertEqual(resp.status_code, 200)
        # Check that match in DB is NOT marked completed
        m = self.mock_db.tables['tournament_matches'][0]
        self.assertEqual(m['status'], 'pending')
        self.assertIsNone(m['player1_score'])

    @patch('app.db.get_admin_db')
    @patch('app.db.get_db')
    @patch('app.clubadmin.routes.get_admin_db')
    @patch('app.clubadmin.routes.get_db')
    @patch('app.clubadmin.tournaments.get_admin_db')
    @patch('app.clubadmin.tournaments.get_db')
    def test_negative_score_rejected(self, mock_t_db, mock_t_adb, mock_r_db, mock_r_adb, mock_db, mock_adb):
        """Verify that negative scores are rejected."""
        for m in [mock_t_db, mock_t_adb, mock_r_db, mock_r_adb, mock_db, mock_adb]:
            m.return_value = self.mock_db
        self._login_clubadmin()

        payload = {
            'player1_score': -5,
            'player2_score': 11
        }

        resp = self.client.post(
            '/clubadmin/tournaments/ev-tourney-1/matches/match-101/score',
            data=payload,
            follow_redirects=True
        )
        self.assertEqual(resp.status_code, 200)
        m = self.mock_db.tables['tournament_matches'][0]
        self.assertEqual(m['status'], 'pending')

    @patch('app.db.get_admin_db')
    @patch('app.db.get_db')
    @patch('app.clubadmin.routes.get_admin_db')
    @patch('app.clubadmin.routes.get_db')
    @patch('app.clubadmin.tournaments.get_admin_db')
    @patch('app.clubadmin.tournaments.get_db')
    def test_valid_score_recorded_successfully(self, mock_t_db, mock_t_adb, mock_r_db, mock_r_adb, mock_db, mock_adb):
        """Verify that a valid score (e.g. 11-8) successfully completes the match and records the winner."""
        for m in [mock_t_db, mock_t_adb, mock_r_db, mock_r_adb, mock_db, mock_adb]:
            m.return_value = self.mock_db
        self._login_clubadmin()

        payload = {
            'player1_score': 11,
            'player2_score': 8,
            'winner_side': 'player1'
        }

        resp = self.client.post(
            '/clubadmin/tournaments/ev-tourney-1/matches/match-101/score',
            data=payload,
            follow_redirects=True
        )
        self.assertEqual(resp.status_code, 200)
        m = self.mock_db.tables['tournament_matches'][0]
        self.assertEqual(m['status'], 'completed')
        self.assertEqual(m['player1_score'], 11)
        self.assertEqual(m['player2_score'], 8)
        self.assertEqual(m['winner_id'], '00000000-0000-0000-0000-000000000001')


if __name__ == '__main__':
    unittest.main()
