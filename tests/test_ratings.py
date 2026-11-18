"""
Unit & Integration Tests for Player Ratings:
- Baseline ratings (ELO and DUPR) by proficiency
- ELO to DUPR linear mapping and boundary clamping (2.00 to 8.00)
- Win/loss rating calculations and walk-in opponent impact
- Profile stat adjustments
"""

import unittest
from app.ratings import elo_to_dupr, get_initial_rating, adjust_profile_stats
from tests.mock_db import MockSupabaseClient

class TestRatings(unittest.TestCase):

    def test_baseline_ratings_by_proficiency(self):
        """Verify baseline ratings match official skill tier mappings."""
        expected_mappings = {
            'novice': (800, 2.00),
            'beginner': (1000, 2.50),
            'intermediate': (1400, 3.50),
            'advanced': (1800, 4.50),
            'pro': (2200, 5.50),
            'unknown_fallback': (1200, 3.00)
        }
        for prof, (expected_elo, expected_dupr) in expected_mappings.items():
            elo, dupr = get_initial_rating(prof)
            self.assertEqual(elo, expected_elo, f"Proficiency {prof} Elo mismatch")
            self.assertEqual(dupr, expected_dupr, f"Proficiency {prof} DUPR mismatch")

    def test_dupr_clamping_bounds(self):
        """Verify that DUPR is clamped between 2.00 and 8.00."""
        # Extremely low Elo
        self.assertEqual(elo_to_dupr(400), 2.00)
        self.assertEqual(elo_to_dupr(0), 2.00)
        self.assertEqual(elo_to_dupr(-500), 2.00)

        # Extremely high Elo
        self.assertEqual(elo_to_dupr(3600), 8.00)
        self.assertEqual(elo_to_dupr(5000), 8.00)

        # Middle ground
        self.assertEqual(elo_to_dupr(1400), 3.50)
        self.assertEqual(elo_to_dupr(1800), 4.50)

    def test_walkin_upset_elo_delta_math(self):
        """Verify Elo math when high-rated registered player plays novice walk-in."""
        r1_registered_elo = 1400
        r2_walkin_elo = 800

        # Win probability for registered player
        expected1 = 1.0 / (1.0 + 10.0 ** ((r2_walkin_elo - r1_registered_elo) / 400.0))
        self.assertGreater(expected1, 0.90)  # > 90% chance to win

        # Small gain on expected win (1 to 5 points)
        new_elo_win = round(r1_registered_elo + 32 * (1.0 - expected1))
        delta_win = new_elo_win - r1_registered_elo
        self.assertGreater(delta_win, 0)
        self.assertLessEqual(delta_win, 5)

        # Large penalty on upset loss (< -25 points)
        new_elo_loss = round(r1_registered_elo + 32 * (0.0 - expected1))
        delta_loss = new_elo_loss - r1_registered_elo
        self.assertLess(delta_loss, -25)

    def test_adjust_profile_stats(self):
        """Verify wins and losses adjustment on profile record."""
        mock_db = MockSupabaseClient({
            'profiles': [
                {
                    'id': 'player-stats-1',
                    'wins': 5,
                    'losses': 2
                }
            ]
        })

        # Record a win (+1 win, +0 loss)
        adjust_profile_stats(mock_db, 'player-stats-1', wins_change=1, losses_change=0)
        prof = mock_db.tables['profiles'][0]
        self.assertEqual(prof['wins'], 6)
        self.assertEqual(prof['losses'], 2)

        # Reversal (-1 win, +1 loss)
        adjust_profile_stats(mock_db, 'player-stats-1', wins_change=-1, losses_change=1)
        prof = mock_db.tables['profiles'][0]
        self.assertEqual(prof['wins'], 5)
        self.assertEqual(prof['losses'], 3)


if __name__ == '__main__':
    unittest.main()
