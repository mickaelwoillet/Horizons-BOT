"""Regression guards for the NOX daily scheduler's post-send bookkeeping."""
import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'cogs' / 'nox_daily_12.py').read_text(encoding='utf-8')


class NoxDeliveryAudit(unittest.TestCase):
    def test_scheduler_compiles(self):
        ast.parse(SOURCE)

    def test_single_post_send_transaction(self):
        start = SOURCE.index('            # Persist delivery and interactive message IDs')
        end = SOURCE.index('            # Optional reply tracking', start)
        block = SOURCE[start:end]
        self.assertEqual(block.count('with engine.connect(DB) as con:'), 1)
        self.assertIn('UPDATE nox_daily_challenges SET message_id=', block)
        self.assertIn('UPDATE nox_daily_polls SET message_id=', block)
        self.assertIn("UPDATE nox_daily_posts SET state='sent'", block)
        self.assertEqual(block.count('con.commit()'), 1)
        self.assertIn('except Exception:', block)

    def test_reply_tracking_after_delivery_commit(self):
        self.assertLess(SOURCE.index("UPDATE nox_daily_posts SET state='sent'"),
                        SOURCE.index('from .nox_interactions import record_post'))

    def test_pre_send_validation_and_ambiguous_send_reservation(self):
        self.assertIn('release_unsent_reservation()', SOURCE)
        self.assertIn('Keep the reservation rather than risk a duplicate publication', SOURCE)


if __name__ == '__main__':
    unittest.main()
