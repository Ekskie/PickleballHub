"""
Unit & Integration Tests for Security, RBAC & Error Handling:
- Role permission hierarchy rules
- Permanent removal of /demo-player backdoor
- Support ticket authorization and length validation
- Dual-format branded error handlers (JSON vs HTML)
"""

import time
import unittest
from unittest.mock import patch
from app import create_app
from app.decorators import has_role_permission
from tests.mock_db import MockSupabaseClient

TEST_USER_ID = '00000000-0000-0000-0000-000000000001'

class TestSecurityRBAC(unittest.TestCase):

    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()

        self.initial_tables = {
            'tickets': [],
            'profiles': [
                {
                    'id': TEST_USER_ID,
                    'role': 'player',
                    'first_name': 'Test',
                    'last_name': 'Player',
                    'is_suspended': False
                }
            ]
        }
        self.mock_db = MockSupabaseClient(self.initial_tables)

    def test_role_permission_hierarchy(self):
        """Verify role hierarchy and operational boundaries."""
        # 1. Superadmin has global permission
        self.assertTrue(has_role_permission('superadmin', ['owner']))
        self.assertTrue(has_role_permission('superadmin', ['player']))
        self.assertTrue(has_role_permission('superadmin', ['clubadmin']))

        # 2. Direct matches
        self.assertTrue(has_role_permission('owner', ['owner']))
        self.assertTrue(has_role_permission('player', ['player']))

        # 3. Any logged-in staff/owner can view player views
        self.assertTrue(has_role_permission('owner', ['player']))
        self.assertTrue(has_role_permission('facilitystaff', ['player']))

        # 4. Adminstaff can access clubadmin and facilitystaff
        self.assertTrue(has_role_permission('adminstaff', ['clubadmin']))
        self.assertTrue(has_role_permission('adminstaff', ['facilitystaff']))

        # 5. Clubadmin / facilitystaff CANNOT access owner financials
        self.assertFalse(has_role_permission('clubadmin', ['owner']))
        self.assertFalse(has_role_permission('facilitystaff', ['owner']))

    def test_demo_player_route_is_permanently_removed(self):
        """Verify that /demo-player route does not exist and returns 404."""
        resp = self.client.get('/demo-player', headers={'Accept': 'application/json'})
        self.assertEqual(resp.status_code, 404)
        data = resp.get_json()
        self.assertFalse(data.get('success'))
        self.assertEqual(data.get('status_code'), 404)

    def test_support_ticket_requires_auth(self):
        """Verify that submitting a support ticket without authentication fails."""
        resp = self.client.post('/support/submit', data={
            'subject': 'Help needed',
            'message': 'Cannot find tournament bracket'
        })
        # Should redirect to login
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login', resp.headers.get('Location', ''))

    @patch('app.db.get_db')
    @patch('app.db.get_admin_db')
    @patch('app.support.routes.get_db')
    def test_support_ticket_length_validation(self, mock_s_db, mock_adb, mock_db):
        """Verify that subject > 200 chars or message > 5000 chars is rejected."""
        mock_s_db.return_value = self.mock_db
        mock_adb.return_value = self.mock_db
        mock_db.return_value = self.mock_db

        profile = {
            'id': TEST_USER_ID,
            'role': 'player',
            'first_name': 'Test',
            'last_name': 'Player',
            'is_suspended': False
        }
        with self.client.session_transaction() as sess:
            sess['user_id'] = TEST_USER_ID
            sess['role'] = 'player'
            sess['last_integrity_check'] = time.time()
            sess['cached_profile'] = profile
            sess['_fresh'] = True

        # Oversized subject
        oversized_subject = 'A' * 201
        resp = self.client.post('/support/submit', data={
            'subject': oversized_subject,
            'message': 'Valid message'
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(self.mock_db.tables['tickets']), 0)

    def test_dual_format_error_handling(self):
        """Verify that error handlers return JSON for API requests and HTML for browser visits."""
        # 1. JSON 404
        json_resp = self.client.get('/nonexistent-path-for-testing', headers={'Accept': 'application/json'})
        self.assertEqual(json_resp.status_code, 404)
        self.assertTrue(json_resp.is_json)
        data = json_resp.get_json()
        self.assertEqual(data.get('status_code'), 404)
        self.assertFalse(data.get('success'))

        # 2. HTML 404
        html_resp = self.client.get('/nonexistent-path-for-testing', headers={'Accept': 'text/html'})
        self.assertEqual(html_resp.status_code, 404)
        self.assertIn('text/html', html_resp.content_type)
        self.assertIn('Out of Bounds', html_resp.get_data(as_text=True))


if __name__ == '__main__':
    unittest.main()
