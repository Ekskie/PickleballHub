"""
Unit & Integration Tests for Centralized Billing & Tier Limits:
- Owner facility and court tier limits (Free, Pro, Elite)
- Player advance booking day limit enforcement
- Clubadmin tournament bracket player cap
- Tier resolution fallbacks
"""

import unittest
from datetime import datetime, timezone, timedelta
from app.billing.tiers import (
    DEFAULT_TIER_CONFIG, get_tier_limits, get_user_tier, check_feature_limit
)
from tests.mock_db import MockSupabaseClient

PH_TZ = timezone(timedelta(hours=8))

class TestBillingTiers(unittest.TestCase):

    def test_tier_limits_retrieval(self):
        """Verify tier limit dictionary definitions."""
        owner_free = get_tier_limits('owner', 'free')
        self.assertEqual(owner_free['max_facilities'], 1)
        self.assertEqual(owner_free['max_courts_per_facility'], 2)
        self.assertFalse(owner_free['peak_pricing_allowed'])

        owner_pro = get_tier_limits('owner', 'pro')
        self.assertEqual(owner_pro['max_facilities'], 3)
        self.assertEqual(owner_pro['max_courts_per_facility'], 8)
        self.assertTrue(owner_pro['peak_pricing_allowed'])

        owner_elite = get_tier_limits('owner', 'elite')
        self.assertGreaterEqual(owner_elite['max_facilities'], 999)
        self.assertTrue(owner_elite['featured_top_pin'])

    def test_owner_max_facilities_limit_check(self):
        """Verify check_feature_limit blocks facility creation when limit reached."""
        # Free owner with 1 existing facility
        chk_free = check_feature_limit(
            {'id': 'owner-1', 'subscription_tier': 'free', 'subscription_status': 'active'},
            'owner',
            'max_facilities',
            current_count=1
        )
        self.assertFalse(chk_free['allowed'])
        self.assertEqual(chk_free['required_tier'], 'pro')
        self.assertIn('Upgrade to Pro', chk_free['message'])

        # Pro owner with 1 existing facility (allowed, limit is 3)
        chk_pro = check_feature_limit(
            {'id': 'owner-2', 'subscription_tier': 'pro', 'subscription_status': 'active'},
            'owner',
            'max_facilities',
            current_count=1
        )
        self.assertTrue(chk_pro['allowed'])

    def test_player_advance_booking_limit(self):
        """Verify player advance booking days check (Free=14 days)."""
        now_ph = datetime.now(PH_TZ).date()

        # Target 5 days ahead (Allowed)
        date_allowed = (now_ph + timedelta(days=5)).strftime('%Y-%m-%d')
        res_allowed = check_feature_limit(
            {'id': 'player-1', 'subscription_tier': 'free'},
            'player',
            'advance_booking_days',
            target_date=date_allowed
        )
        self.assertTrue(res_allowed['allowed'])

        # Target 25 days ahead (Blocked)
        date_blocked = (now_ph + timedelta(days=25)).strftime('%Y-%m-%d')
        res_blocked = check_feature_limit(
            {'id': 'player-1', 'subscription_tier': 'free'},
            'player',
            'advance_booking_days',
            target_date=date_blocked
        )
        self.assertFalse(res_blocked['allowed'])
        self.assertIn('Reservations can be made up to 14 days in advance', res_blocked['message'])

    def test_clubadmin_bracket_size_limit(self):
        """Verify Free clubadmin bracket cap (max 8 players)."""
        # 8 players on Free plan (allowed)
        chk_8 = check_feature_limit(
            {'id': 'admin-1', 'subscription_tier': 'free', 'subscription_status': 'active'},
            'clubadmin',
            'max_tournament_bracket',
            current_count=8
        )
        self.assertTrue(chk_8['allowed'])

        # 9 players on Free plan (blocked, requires Pro for up to 64)
        chk_9 = check_feature_limit(
            {'id': 'admin-1', 'subscription_tier': 'free', 'subscription_status': 'active'},
            'clubadmin',
            'max_tournament_bracket',
            current_count=9
        )
        self.assertFalse(chk_9['allowed'])
        self.assertIn('Upgrade to Pro Club Pass', chk_9['message'])


if __name__ == '__main__':
    unittest.main()
