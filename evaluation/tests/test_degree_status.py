"""Tests for evidence-backed degree status resolution and guardrails."""
import asyncio
import unittest
from unittest.mock import patch

from backend.degree_status import extract_degree_evidence, resolve_degree_status, check_degree_retraction


class DegreeStatusEvidenceTests(unittest.TestCase):
    def test_explicit_no_statements(self):
        cases = [
            "I completed secondary school, but I don't have a bachelor's degree.",
            "I do not have a degree",
            "I don't have any degree",
            "I haven't got a bachelor degree",
            "I have no bachelor's degree",
            "I am without a bachelor's degree",
            "I never completed a degree",
            "I don't hold a degree",
            "I currently have no degree",
            "I completed high school; for me, no bachelor degree.",
            "I lack a bachelor's degree.",
        ]
        for text in cases:
            status, match = extract_degree_evidence(text)
            self.assertIs(status, False, f"Expected False for: {text!r}")
            self.assertIsNotNone(match)

    def test_explicit_yes_statements(self):
        cases = [
            "I have a bachelor's degree in computer science",
            "I hold a bachelor degree in arts",
            "I completed my bachelor's degree in 2020",
            "I already have a degree in mathematics",
            "I already have a bachelor degree",
            "I graduated with a bachelor of science",
            "I graduated from university with a bachelor degree",
            "I do have a bachelor's degree",
            "I've completed an undergraduate degree.",
            # Regression case 4: Factual disclosure with subsequent aspiration for another field
            "I have a bachelor's degree and want to study cloud computing.",
            "I hold a degree in business and hope to do a master of IT.",
        ]
        for text in cases:
            status, match = extract_degree_evidence(text)
            self.assertIs(status, True, f"Expected True for: {text!r}")
            self.assertIsNotNone(match)

    def test_counterexample_regressions_must_remain_none(self):
        # Specific regressions reported by audit
        counterexamples = [
            # Regression 1: General/policy question mistreated as personal fact
            "Can someone apply without a bachelor's degree?",
            "Can anyone enrol without a degree?",
            "Is it possible for a student to apply without a bachelor degree?",
            # Regression 2: Sub-degree qualification mistreated as bachelor degree
            "I have a university diploma.",
            "I have an undergraduate diploma.",
            "I have a tertiary diploma in business.",
            "I completed a certificate in IT.",
            # Regression 3: Hypothetical statement mistreated as factual declaration
            "If I have a bachelor's degree, would that help?",
            "Suppose I have a bachelor's degree, what are the fees?",
            "What if I have an undergraduate degree, does that count?",
            "Even if I have a degree, would I still need to submit a portfolio?",
            # Regression 4: Someone else's statement / reported speech
            "My sister said, “I have a bachelor's degree.”",
            "My brother told me, 'I have a bachelor degree.'",
            "My friend mentioned, \"I have an undergraduate degree.\"",
            # Regression 5: Extended hypotheticals
            "Let's suppose I have a bachelor's degree.",
            "Let's say I have a bachelor's degree.",
            "Say I have a bachelor degree.",
            # Regression 6: In-progress / incomplete study
            "I have a degree in progress.",
            "I have a bachelor's degree in progress.",
            "I have an incomplete degree.",
            "I have an unfinished bachelor's degree.",
        ]
        for text in counterexamples:
            status, match = extract_degree_evidence(text)
            self.assertIsNone(status, f"Expected None for counterexample: {text!r}, got {status} ({match})")

    def test_aspirational_and_unspecified_statements_remain_none(self):
        cases = [
            # Overseas secondary schooling / undergraduate interest (discovery-international)
            "Hi Clara! I'm interested in studying computing at Kingsford University. "
            "I've completed my secondary qualification overseas and I'm trying to figure "
            "out what my options are for undergraduate courses as an international student.",
            # Aspirational / goal statements targeting degrees
            "I want a bachelor degree in IT",
            "I want to get a degree",
            "I need a bachelor's degree to get promoted",
            "I am looking for a degree in cybersecurity",
            "I hope to get a bachelor degree",
            "I am trying to find a degree",
            "I am studying towards a bachelor's degree",
            "I'm planning to enrol in a bachelor program",
            "I wish to pursue an undergraduate degree",
            # School leaver / work history / questions
            "I finished high school last year with an ATAR of 82",
            "I have 3 years of IT support experience",
            "Can I get a degree without an ATAR?",
            "How do I apply for a bachelor's degree?",
            "Does this degree have part-time availability?",
        ]
        for text in cases:
            status, match = extract_degree_evidence(text)
            self.assertIsNone(status, f"Expected None for: {text!r}, got {status} ({match})")
            self.assertIsNone(match)

    def test_missing_session_context_produces_none(self):
        # Line 104 bug: Missing session context must NEVER silently trust proposed values
        for proposed_val in (False, True, None):
            res = resolve_degree_status(None, proposed=proposed_val)
            self.assertIsNone(res["effective"], f"Expected None for proposed={proposed_val} with missing context")
            self.assertIs(res["proposed"], proposed_val)
            self.assertEqual(res["source"], "missing_context")
            self.assertIn("cannot verify degree status from evidence", res["reason"])

    def test_resolution_unsupported_model_proposal_guarded_to_none(self):
        # Model proposes False based on secondary qualification overseas
        messages = [
            {
                "id": 1,
                "text": "Hi Clara! I completed my secondary qualification overseas and want undergraduate computing.",
            }
        ]
        res = resolve_degree_status(messages, proposed=False)
        self.assertIsNone(res["effective"])
        self.assertIs(res["proposed"], False)
        self.assertEqual(res["source"], "unsupported")
        self.assertIsNone(res["evidence"])
        self.assertIn("no explicit evidence", res["reason"])

    def test_resolution_supported_model_proposal(self):
        messages = [
            {
                "id": 1,
                "text": "I completed secondary school, but I don't have a bachelor's degree.",
            }
        ]
        res = resolve_degree_status(messages, proposed=False)
        self.assertIs(res["effective"], False)
        self.assertIs(res["proposed"], False)
        self.assertEqual(res["source"], "evidence")
        self.assertEqual(res["evidence"]["message_id"], 1)

    def test_resolution_positive_evidence(self):
        messages = [
            {"id": 1, "text": "I already have a bachelor's degree in biology."},
            {"id": 2, "text": "Now I want to study postgraduate data science."},
        ]
        res = resolve_degree_status(messages, proposed=True)
        self.assertIs(res["effective"], True)
        self.assertIs(res["proposed"], True)
        self.assertEqual(res["source"], "evidence")
        self.assertEqual(res["evidence"]["message_id"], 1)

    def test_resolution_unspecified_when_both_none(self):
        messages = [
            {"id": 1, "text": "I'm interested in computer science courses."}
        ]
        res = resolve_degree_status(messages, proposed=None)
        self.assertIsNone(res["effective"])
        self.assertIsNone(res["proposed"])
        self.assertEqual(res["source"], "unspecified")

    def test_resolution_contradiction_overridden_by_student_evidence(self):
        # Student says they have a degree, model erroneously proposed False
        messages = [
            {"id": 1, "text": "I have a bachelor of commerce from 2019."}
        ]
        res = resolve_degree_status(messages, proposed=False)
        self.assertIs(res["effective"], True)
        self.assertIs(res["proposed"], False)
        self.assertEqual(res["source"], "contradicted")
        self.assertEqual(res["evidence"]["message_id"], 1)

    def test_corrections_and_retractions_across_messages(self):
        # 1. Message 1: No degree. Message 2: Corrects to having a degree.
        messages_to_yes = [
            {"id": 1, "text": "I don't have a degree."},
            {"id": 2, "text": "Wait, sorry, I actually do have a bachelor's degree from overseas."},
        ]
        res_yes = resolve_degree_status(messages_to_yes, proposed=True)
        self.assertIs(res_yes["effective"], True)
        self.assertEqual(res_yes["evidence"]["message_id"], 2)

        # 2. Message 1: Has qualification. Message 2: Clarifies it is a diploma, not a degree.
        messages_to_no = [
            {"id": 1, "text": "I have a tertiary qualification."},
            {"id": 2, "text": "To be clear, it is a diploma, I do not have a bachelor degree."},
        ]
        res_no = resolve_degree_status(messages_to_no, proposed=False)
        self.assertIs(res_no["effective"], False)
        self.assertEqual(res_no["evidence"]["message_id"], 2)

        # 3. Message 1: Has degree. Message 2: Retracts / declares uncertainty ("disregard what I said").
        messages_retract = [
            {"id": 1, "text": "I have a bachelor's degree in engineering."},
            {"id": 2, "text": "Actually, disregard what I said earlier about having a degree, that was a mistake."},
        ]
        res_retract = resolve_degree_status(messages_retract, proposed=True)
        self.assertIsNone(res_retract["effective"])
        self.assertEqual(res_retract["source"], "retracted")
        self.assertIn("retracted or called into doubt", res_retract["reason"])

        # 4. Message 1: Has degree. Message 2: Unsure if student's OWN degree is accredited/recognized.
        messages_unsure = [
            {"id": 1, "text": "I hold a bachelor degree from abroad."},
            {"id": 2, "text": "I'm not sure if my degree is accredited in Australia though."},
        ]
        res_unsure = resolve_degree_status(messages_unsure, proposed=True)
        self.assertIsNone(res_unsure["effective"])
        self.assertEqual(res_unsure["source"], "retracted")

        # 5. Identity correction: "that was my brother, not me" clears prior claim
        messages_identity = [
            {"id": 1, "text": "I have a bachelor's degree in engineering."},
            {"id": 2, "text": "Sorry, that was my brother, not me."},
        ]
        res_id = resolve_degree_status(messages_identity, proposed=True)
        self.assertIsNone(res_id["effective"])
        self.assertEqual(res_id["source"], "retracted")

        # 6. Course accreditation query: asking about a prospective university course does NOT clear personal degree
        messages_course_inquiry = [
            {"id": 1, "text": "I have a bachelor's degree in business."},
            {"id": 2, "text": "Is the Kingsford cybersecurity degree accredited? I'm not sure if that course is recognized."},
        ]
        res_course = resolve_degree_status(messages_course_inquiry, proposed=True)
        self.assertIs(res_course["effective"], True)
        self.assertEqual(res_course["source"], "evidence")
        self.assertEqual(res_course["evidence"]["message_id"], 1)

        # 7. Compound replacement: Retraction + explicit replacement declaration in the same message
        messages_compound = [
            {"id": 1, "text": "I have a bachelor's degree."},
            {"id": 2, "text": "Ignore my earlier comment. I do not have a bachelor's degree."},
        ]
        res_compound = resolve_degree_status(messages_compound, proposed=False)
        self.assertIs(res_compound["effective"], False)
        self.assertEqual(res_compound["source"], "evidence")
        self.assertEqual(res_compound["evidence"]["message_id"], 2)

        # 8. Within-turn ordering: Declaration followed by retraction in the same message
        messages_decl_then_retract = [
            {"id": 1, "text": "I have a bachelor's degree. Actually, scratch that."}
        ]
        res_decl_retract = resolve_degree_status(messages_decl_then_retract, proposed=True)
        self.assertIsNone(res_decl_retract["effective"])
        self.assertEqual(res_decl_retract["source"], "retracted")

        # 9. Multi-turn cycle: Declaration -> Identity correction -> Later valid assertion
        messages_cycle = [
            {"id": 1, "text": "I hold a bachelor degree."},
            {"id": 2, "text": "Sorry, that was my brother, not me."},
            {"id": 3, "text": "Wait, I actually do have a bachelor's degree from another university."},
        ]
        res_cycle = resolve_degree_status(messages_cycle, proposed=True)
        self.assertIs(res_cycle["effective"], True)
        self.assertEqual(res_cycle["source"], "evidence")
        self.assertEqual(res_cycle["evidence"]["message_id"], 3)


class ToolGuardIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from backend import tools
        async def sink(payload): pass
        self.sid = "test-guard-session"
        tools.register_display_callback(self.sid, asyncio.get_running_loop(), sink)
        self.token = tools.bind_display_session(self.sid)

    async def asyncTearDown(self):
        from backend import tools
        try:
            tools.reset_display_session(self.token)
        finally:
            tools.unregister_display_callback(self.sid)

    def test_search_courses_guards_unsupported_model_inference(self):
        from backend import tools

        sample_courses = [
            {
                "code": "CS101",
                "name": "Bachelor of Computer Science",
                "faculty": "Engineering & Technology",
                "level": "Undergraduate",
                "study_mode": "Full-time",
                "duration_years": 3.0,
                "atar_cutoff": 85,
                "entry_requirements": None,
                "annual_fee_aud": 14500,
                "career_outcomes": "Graduates work as software engineers.",
                "similarity": 0.85,
            },
            {
                "code": "DS501",
                "name": "Master of Data Science",
                "faculty": "Engineering & Technology",
                "level": "Postgraduate",
                "study_mode": "Full-time",
                "duration_years": 2.0,
                "atar_cutoff": None,
                "entry_requirements": "Bachelor degree in quantitative field with credit average (GPA 5.0/7.0) or above",
                "annual_fee_aud": 18000,
                "career_outcomes": "Graduates work as data scientists.",
                "similarity": 0.80,
            },
        ]

        # Student only mentioned secondary qualification
        tools.record_student_message(
            "I completed my secondary qualification overseas and want undergraduate computing.",
            "typed",
        )

        with patch.object(tools, "_course_candidates", return_value=sample_courses):
            # Model attempts unsupported inference has_bachelor_degree=False
            res = tools.search_courses("computing", has_bachelor_degree=False)

            # Model proposed value is preserved
            self.assertIs(res["proposed_has_bachelor_degree"], False)
            # Tool effective value is guarded to None
            self.assertIsNone(res["effective_has_bachelor_degree"])
            self.assertEqual(res["degree_status"]["source"], "unsupported")

            # Postgrad degree check should be 'unknown', NOT 'unmet'
            names = [c["name"] for c in res["courses"]]
            self.assertIn("Master of Data Science", names)
            ds = next(c for c in res["courses"] if c["name"] == "Master of Data Science")
            self.assertEqual(ds["suitability"]["status"], "unknown")

    def test_search_courses_accepts_supported_explicit_no(self):
        from backend import tools

        sample_courses = [
            {
                "code": "DS501",
                "name": "Master of Data Science",
                "faculty": "Engineering & Technology",
                "level": "Postgraduate",
                "study_mode": "Full-time",
                "duration_years": 2.0,
                "atar_cutoff": None,
                "entry_requirements": "Bachelor degree in quantitative field with credit average (GPA 5.0/7.0) or above",
                "annual_fee_aud": 18000,
                "career_outcomes": "Graduates work as data scientists.",
                "similarity": 0.80,
            },
        ]

        # Student explicitly states no degree
        tools.record_student_message(
            "I completed secondary school, but I don't have a bachelor's degree.",
            "typed",
        )

        with patch.object(tools, "_course_candidates", return_value=sample_courses):
            res = tools.search_courses("data science", has_bachelor_degree=False)
            self.assertIs(res["proposed_has_bachelor_degree"], False)
            self.assertIs(res["effective_has_bachelor_degree"], False)
            self.assertEqual(res["degree_status"]["source"], "evidence")
            # Because effective is False and degree is required, DS501 is excluded as unmet
            self.assertEqual(res["count"], 0)
            self.assertEqual(len(res["excluded_examples"]), 1)
            self.assertEqual(res["excluded_examples"][0]["suitability"]["status"], "unmet")


if __name__ == "__main__":
    unittest.main()
