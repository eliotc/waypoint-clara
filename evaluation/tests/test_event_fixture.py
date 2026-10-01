from datetime import datetime, timedelta, timezone
import unittest
from evaluation.event_fixture import rebase_event, ZONE


class EventFixtureTests(unittest.TestCase):
    def test_year_rollover_removes_calendar_name_preserves_duration_and_local_time(self):
        start = datetime(2026, 7, 25, 10, tzinfo=ZONE)
        end = start + timedelta(minutes=90)
        anchor = datetime(2026, 12, 30, 23, tzinfo=timezone.utc)
        title, description, new_start, new_end = rebase_event(
            7, 'Saturday Campus Tour', 'No registration required.', start, end, anchor)
        self.assertEqual(title, 'Campus Tour')
        self.assertEqual(description, 'No registration required.')
        self.assertEqual(new_start.hour, 10)
        self.assertEqual(new_start.year, 2027)
        self.assertEqual(new_end - new_start.astimezone(timezone.utc), timedelta(minutes=90))
        self.assertGreater(new_start, anchor)

    def test_deadline_text_is_removed_without_inventing_replacement_date(self):
        start = datetime(2026, 9, 9, 17, 30, tzinfo=ZONE)
        title, description, _, _ = rebase_event(21, 'VTAC Application Workshop',
            'Deadline 30 September for 2027 entry.', start, start + timedelta(hours=1), start)
        self.assertEqual(title, 'VTAC Application Workshop')
        self.assertNotIn('September', description)
        self.assertNotIn('2027', description)
        self.assertIn('find applicable deadlines', description)
