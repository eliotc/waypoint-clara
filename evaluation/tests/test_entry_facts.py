"""Course tools must not let missing prerequisites hide a recorded ATAR cutoff."""
import unittest

from backend import tools


class EntryFactsTests(unittest.TestCase):
    def test_recorded_atar_is_known_when_other_requirements_are_missing(self):
        # Shape of the Bachelor of Computer Science record: ATAR 85, no prerequisite text.
        facts = tools._entry_facts({"atar_cutoff": 85, "entry_requirements": None})
        self.assertEqual(len(facts["known"]), 1)
        self.assertIn("85", facts["known"][0])
        self.assertIn("not a guarantee", facts["known"][0])
        self.assertNotIn("ATAR cutoff", facts["not_recorded"])
        self.assertEqual(facts["not_recorded"], ["Prerequisite subjects or other entry requirements"])

    def test_recorded_requirements_are_known(self):
        facts = tools._entry_facts({"atar_cutoff": 80, "entry_requirements": "Year 12 Mathematical Methods"})
        self.assertEqual(len(facts["known"]), 2)
        self.assertIn("Year 12 Mathematical Methods", facts["known"][1])
        self.assertEqual(facts["not_recorded"], [])

    def test_missing_atar_and_requirements_are_both_unrecorded(self):
        facts = tools._entry_facts({"atar_cutoff": None, "entry_requirements": "  "})
        self.assertEqual(facts["known"], [])
        self.assertEqual(facts["not_recorded"], ["ATAR cutoff", "Prerequisite subjects or other entry requirements"])

    def test_evidence_limits_no_longer_imply_atar_is_unknown(self):
        self.assertIn("entry_facts", tools.COURSE_EVIDENCE_LIMITS)
        self.assertNotIn("Null entry requirements mean unknown", tools.COURSE_EVIDENCE_LIMITS)


if __name__ == "__main__":
    unittest.main()
