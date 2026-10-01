"""Unit tests for professional IT experience resolution and boundary enforcement."""
import asyncio
import unittest
from unittest.mock import patch

from backend.experience_status import (
    classify_experience_clause,
    resolve_it_experience,
)


class ITExperienceEvidenceTests(unittest.TestCase):
    def test_explicit_positive_it_experience(self):
        cases = [
            ("I've been working in IT support for three years, and I'm interested in cloud computing.", 3.0),
            ("I have 5 years of professional IT experience as a software developer.", 5.0),
            ("I worked in technical support for two years.", 2.0),
            ("I worked in cybersecurity for 4 years.", 4.0),
            ("I have 1 year of professional IT experience.", 1.0),
            ("I've got 2.5 years working in cloud computing.", 2.5),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                res = resolve_it_experience([{"id": "msg-1", "text": text}], proposed=None)
                self.assertEqual(res["effective"], expected)
                self.assertEqual(res["source"], "evidence")
                self.assertIsNotNone(res["evidence"])

    def test_explicit_zero_it_experience(self):
        cases = [
            "I have no IT experience at all.",
            "I don't have any IT experience.",
            "I have zero years of professional IT experience.",
            "I've never worked in IT.",
            "I have no tech experience.",
            "No IT experience for me, I'm a fresh high school graduate.",
        ]
        for text in cases:
            with self.subTest(text=text):
                res = resolve_it_experience([{"id": "msg-1", "text": text}], proposed=0)
                self.assertEqual(res["effective"], 0.0)
                self.assertEqual(res["source"], "evidence")

    def test_unrelated_work_experience_remains_none(self):
        unrelated_cases = [
            "I've been working in retail for three years.",
            "I have 5 years of hospitality experience as a barista.",
            "I worked in sales and customer service for four years.",
            "I have 2 years of experience in accounting.",
            "I've been working in construction for ten years.",
            "I have 3 years of work experience as a nurse.",
        ]
        for text in unrelated_cases:
            with self.subTest(text=text):
                # When model proposes 0 on unrelated experience, it MUST be guarded to None
                res = resolve_it_experience([{"id": "msg-1", "text": text}], proposed=0)
                self.assertIsNone(res["effective"])
                self.assertEqual(res["source"], "unsupported")

    def test_unmentioned_and_secondary_education_remains_none(self):
        unmentioned_cases = [
            "Hi Clara! I'm interested in studying computing at Kingsford University. I've completed my secondary qualification overseas",
            "I'm a school leaver and got an ATAR of 82. I'm looking to study full-time.",
            "Can you tell me about the Bachelor of Cybersecurity?",
            "I'm looking for an undergraduate cybersecurity course.",
        ]
        for text in unmentioned_cases:
            with self.subTest(text=text):
                # Model proposing 0 without disclosure must be intercepted
                res = resolve_it_experience([{"id": "msg-1", "text": text}], proposed=0)
                self.assertIsNone(res["effective"])
                self.assertEqual(res["source"], "unsupported")

                # Model proposing None remains unspecified
                res_none = resolve_it_experience([{"id": "msg-1", "text": text}], proposed=None)
                self.assertIsNone(res_none["effective"])
                self.assertEqual(res_none["source"], "unspecified")

    def test_hypothetical_and_third_person_remains_none(self):
        cases = [
            "What if I have 3 years of IT experience?",
            "Let's suppose I have 5 years of IT experience, would that qualify me?",
            "Imagine I have 2 years in IT support.",
            "My brother has 5 years of IT experience.",
            "My colleague said he has 4 years in cybersecurity.",
        ]
        for text in cases:
            with self.subTest(text=text):
                res = resolve_it_experience([{"id": "msg-1", "text": text}], proposed=3.0)
                self.assertIsNone(res["effective"])
                self.assertEqual(res["source"], "unsupported")

    def test_corrections_and_retractions_across_messages(self):
        # Case 1: Student claims 3 years IT support, then corrects that they worked in retail not IT
        msgs1 = [
            {"id": "msg-1", "text": "I've been working in IT support for three years."},
            {"id": "msg-2", "text": "Actually, scratch that, I worked in retail, not IT."},
        ]
        res1 = resolve_it_experience(msgs1, proposed=3.0)
        self.assertIsNone(res1["effective"])
        self.assertEqual(res1["source"], "retracted")

        # Case 2: Student updates experience from 3 years to 1 year
        msgs2 = [
            {"id": "msg-1", "text": "I have three years of professional IT experience."},
            {"id": "msg-2", "text": "Actually I made a mistake, I worked in IT for one year."},
        ]
        res2 = resolve_it_experience(msgs2, proposed=1.0)
        self.assertEqual(res2["effective"], 1.0)
        self.assertEqual(res2["source"], "evidence")

        # Case 3: Student claims IT experience, then states they have no IT experience
        msgs3 = [
            {"id": "msg-1", "text": "I worked in IT."},
            {"id": "msg-2", "text": "Actually I don't have any IT experience, sorry."},
        ]
        res3 = resolve_it_experience(msgs3, proposed=0.0)
        self.assertEqual(res3["effective"], 0.0)
        self.assertEqual(res3["source"], "evidence")

    def test_codex_counterexamples(self):
        # 1. Policy question about requirement
        res1 = resolve_it_experience([{"id": 1, "text": "Does this require three years of IT experience?"}], proposed=None)
        self.assertIsNone(res1["effective"])
        self.assertEqual(res1["source"], "unspecified")

        # 2. Negated duration threshold
        res2 = resolve_it_experience([{"id": 1, "text": "I do not have three years of IT experience."}], proposed=None)
        self.assertIsNone(res2["effective"])
        self.assertEqual(res2["source"], "unspecified")

        # 3. Identity correction across messages
        res3 = resolve_it_experience([
            {"id": 1, "text": "I have three years of professional IT experience."},
            {"id": 2, "text": "Sorry, that was my brother, not me."},
        ], proposed=None)
        self.assertIsNone(res3["effective"])
        self.assertEqual(res3["source"], "retracted")

        # 4. Non-IT attribution correction
        res4 = resolve_it_experience([
            {"id": 1, "text": "I have three years of professional IT experience."},
            {"id": 2, "text": "I worked in retail, not IT."},
        ], proposed=None)
        self.assertIsNone(res4["effective"])
        self.assertEqual(res4["source"], "retracted")

        # 5. Positive control with mixed employment
        res5 = resolve_it_experience([
            {"id": 1, "text": "I have three years of professional IT experience and five years in retail."}
        ], proposed=None)
        self.assertEqual(res5["effective"], 3.0)
        self.assertEqual(res5["source"], "evidence")

    def test_codex_counterexamples_4690d8f(self):
        # 1. Policy paraphrase ending with question mark
        res1 = resolve_it_experience([{"id": 1, "text": "Is three years of IT experience required?"}], proposed=3.0)
        self.assertIsNone(res1["effective"])
        self.assertEqual(res1["source"], "unsupported")

        # 2. Hypothetical compound with conditional 'If'
        res2 = resolve_it_experience([{"id": 1, "text": "If I move to Melbourne and have three years of IT experience, could I apply?"}], proposed=3.0)
        self.assertIsNone(res2["effective"])
        self.assertEqual(res2["source"], "unsupported")

        # 3. Correction replacement within turn
        res3 = resolve_it_experience([
            {"id": 1, "text": "I have three years of professional IT experience."},
            {"id": 2, "text": "Actually I made a mistake, I worked in IT for 1 year."},
        ], proposed=1.0)
        self.assertEqual(res3["effective"], 1.0)
        self.assertEqual(res3["source"], "evidence")

        # 4. Negation of prior claim
        res4 = resolve_it_experience([
            {"id": 1, "text": "I have three years of professional IT experience."},
            {"id": 2, "text": "Actually, I do not have three years of IT experience."},
        ], proposed=None)
        self.assertIsNone(res4["effective"])
        self.assertEqual(res4["source"], "retracted")

        # 5. Unrelated correction preserves prior established experience
        res5 = resolve_it_experience([
            {"id": 1, "text": "I have three years of professional IT experience."},
            {"id": 2, "text": "My brother wants Business, not me."},
        ], proposed=3.0)
        self.assertEqual(res5["effective"], 3.0)
        self.assertEqual(res5["source"], "evidence")

        # 6. Professional vs total experience distinguished
        res6 = resolve_it_experience([
            {"id": 1, "text": "I have three years of IT experience, but only one year was professional; the rest was coursework."}
        ], proposed=1.0)
        self.assertIsNone(res6["effective"])
        self.assertTrue(res6["needs_clarification"])

    def test_codex_counterexamples_c13eeb2a(self):
        # 1. Reported speech / other attribution
        res1 = resolve_it_experience([
            {"id": 1, "text": "My sister said, I have three years of professional IT experience."}
        ], proposed=None)
        self.assertIsNone(res1["effective"])
        self.assertEqual(res1["source"], "unspecified")

        # 2. Non-IT antecedent for professional refinement
        res2 = resolve_it_experience([
            {"id": 1, "text": "I worked in retail for five years; three years were professional."}
        ], proposed=None)
        self.assertIsNone(res2["effective"])
        self.assertEqual(res2["source"], "unspecified")

        # 3. Embedded hypothetical
        res3 = resolve_it_experience([
            {"id": 1, "text": "For example, if I have three years of IT experience, would that help?"}
        ], proposed=None)
        self.assertIsNone(res3["effective"])
        self.assertEqual(res3["source"], "unspecified")

        # 4. Interrogative with first person
        res4 = resolve_it_experience([
            {"id": 1, "text": "Do I have to have three years of IT experience?"}
        ], proposed=None)
        self.assertIsNone(res4["effective"])
        self.assertEqual(res4["source"], "unspecified")

        # 5. Separate question following no degree disclosure
        res5 = resolve_it_experience([
            {"id": 1, "text": "I have no degree. Does this require three years of IT experience?"}
        ], proposed=None)
        self.assertIsNone(res5["effective"])
        self.assertEqual(res5["source"], "unspecified")

        # 6. Third-person zero experience disclosure
        res6 = resolve_it_experience([
            {"id": 1, "text": "My sister has no IT experience."}
        ], proposed=None)
        self.assertIsNone(res6["effective"])
        self.assertEqual(res6["source"], "unspecified")

        # 7. Positive control: 3-year IT support with no bachelor degree
        res7 = resolve_it_experience([
            {"id": 1, "text": "I've been working in IT support for three years, and I don't have a bachelor's degree."}
        ], proposed=3.0)
        self.assertEqual(res7["effective"], 3.0)
        self.assertEqual(res7["source"], "evidence")

    def test_boundary_paraphrases_and_positive_controls(self):
        # A. Additional reported speech paraphrases
        cases_reported = [
            "My brother told me, I have 4 years in software engineering.",
            "My boss said I have five years of IT experience.",
            "He said 'I have two years in tech'.",
        ]
        for text in cases_reported:
            with self.subTest(reported=text):
                res = resolve_it_experience([{"id": 1, "text": text}], proposed=None)
                self.assertIsNone(res["effective"])

        # B. Non-IT antecedents with professional refinement
        cases_non_it = [
            "I spent 6 years in nursing; 2 years were professional.",
            "I worked in hospitality for 4 years; 2 years were professional.",
            "I have five years in sales, but only two years were professional.",
        ]
        for text in cases_non_it:
            with self.subTest(non_it=text):
                res = resolve_it_experience([{"id": 1, "text": text}], proposed=None)
                self.assertIsNone(res["effective"])

        # C. Embedded hypotheticals with varied introductory clauses
        cases_hypothetical = [
            "Say, if I have 3 years of IT experience, does that work?",
            "Assuming I have four years in tech, am I eligible?",
            "What if I have two years of programming experience?",
        ]
        for text in cases_hypothetical:
            with self.subTest(hypothetical=text):
                res = resolve_it_experience([{"id": 1, "text": text}], proposed=None)
                self.assertIsNone(res["effective"])

        # D. Questions with first person pronouns
        cases_questions = [
            "Could I apply if I need three years of IT experience?",
            "Would three years of IT experience count?",
            "Am I required to have 3 years in IT?",
        ]
        for text in cases_questions:
            with self.subTest(question=text):
                res = resolve_it_experience([{"id": 1, "text": text}], proposed=None)
                self.assertIsNone(res["effective"])

        # E. Other people's zero experience
        cases_other_zero = [
            "My friend doesn't have any IT experience.",
            "Someone told me they have no tech background.",
            "My colleague has zero years in software.",
        ]
        for text in cases_other_zero:
            with self.subTest(other_zero=text):
                res = resolve_it_experience([{"id": 1, "text": text}], proposed=None)
                self.assertIsNone(res["effective"])

        # F. Positive controls
        cases_positive = [
            ("I worked in software engineering for 4 years and have no degree.", 4.0),
            ("I've been working as a network administrator for 3 years.", 3.0),
            ("I worked in IT support for two years.", 2.0),
        ]
        for text, exp in cases_positive:
            with self.subTest(positive=text):
                res = resolve_it_experience([{"id": 1, "text": text}], proposed=exp)
                self.assertEqual(res["effective"], exp)
                self.assertEqual(res["source"], "evidence")

    def test_missing_session_context_produces_none(self):
        res = resolve_it_experience(None, proposed=3.0)
        self.assertIsNone(res["effective"])
        self.assertEqual(res["source"], "missing_context")


class ToolGuardExperienceIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from backend import tools
        async def sink(payload): pass
        self.sid = "test-experience-guard-session"
        tools.register_display_callback(self.sid, asyncio.get_running_loop(), sink)
        self.token = tools.bind_display_session(self.sid)

    async def asyncTearDown(self):
        from backend import tools
        try:
            tools.reset_display_session(self.token)
        finally:
            tools.unregister_display_callback(self.sid)

    def test_search_courses_guards_unsupported_zero_experience(self):
        from backend import tools

        sample_courses = [
            {
                "code": "GC-CC",
                "name": "Graduate Certificate in Cloud Computing",
                "faculty": "Engineering & Technology",
                "level": "Postgraduate",
                "study_mode": "Online",
                "duration_years": 0.5,
                "atar_cutoff": None,
                "entry_requirements": "Bachelor degree in IT/quantitative field, or 2+ years of professional IT experience",
                "annual_fee_aud": 12000,
                "career_outcomes": "Cloud architect.",
                "similarity": 0.85,
            },
        ]

        # Student only mentioned secondary qualification overseas, no degree, no IT experience
        tools.record_student_message(
            "Hi Clara! I completed my secondary qualification overseas and want undergraduate computing.",
            "typed",
        )

        with patch.object(tools, "_course_candidates", return_value=sample_courses):
            # Model attempts unsupported inference professional_it_years=0 and has_bachelor_degree=False
            res = tools.search_courses("computing", has_bachelor_degree=False, professional_it_years=0)

            # Model proposed values preserved
            self.assertEqual(res["proposed_professional_it_years"], 0)
            self.assertIs(res["proposed_has_bachelor_degree"], False)

            # Tool effective values guarded to None
            self.assertIsNone(res["effective_professional_it_years"])
            self.assertIsNone(res["effective_has_bachelor_degree"])
            self.assertEqual(res["it_experience_status"]["source"], "unsupported")

            # Entry requirement check must be unknown, NOT unmet (guarded from exclusion)
            course = res["courses"][0]
            self.assertEqual(course["suitability"]["status"], "unknown")

    def test_search_courses_accepts_supported_it_experience(self):
        from backend import tools

        sample_courses = [
            {
                "code": "GC-CC",
                "name": "Graduate Certificate in Cloud Computing",
                "faculty": "Engineering & Technology",
                "level": "Postgraduate",
                "study_mode": "Online",
                "duration_years": 0.5,
                "atar_cutoff": None,
                "entry_requirements": "Bachelor degree in IT/quantitative field, or 2+ years of professional IT experience",
                "annual_fee_aud": 12000,
                "career_outcomes": "Cloud architect.",
                "similarity": 0.85,
            },
        ]

        # Student disclosed 3 years IT support and no degree
        tools.record_student_message(
            "I've been working in IT support for three years, and I don't have a bachelor's degree.",
            "typed",
        )

        with patch.object(tools, "_course_candidates", return_value=sample_courses):
            res = tools.search_courses("cloud", has_bachelor_degree=False, professional_it_years=3)
            self.assertEqual(res["effective_professional_it_years"], 3.0)
            self.assertEqual(res["effective_has_bachelor_degree"], False)
            self.assertEqual(res["it_experience_status"]["source"], "evidence")

            # Because experience >= 2, entry requirement is met via experience route
            course = res["courses"][0]
            entry_check = next(c for c in course["suitability"]["checks"] if c["field"] == "entry_requirements")
            self.assertEqual(entry_check["status"], "met")

    def test_unrelated_employment_does_not_create_eligibility_or_exclusion(self):
        from backend import tools

        sample_courses = [
            {
                "code": "GC-CC",
                "name": "Graduate Certificate in Cloud Computing",
                "faculty": "Engineering & Technology",
                "level": "Postgraduate",
                "study_mode": "Online",
                "duration_years": 0.5,
                "atar_cutoff": None,
                "entry_requirements": "Bachelor degree in IT/quantitative field, or 2+ years of professional IT experience",
                "annual_fee_aud": 12000,
                "career_outcomes": "Cloud architect.",
                "similarity": 0.85,
            },
        ]

        # Student disclosed retail experience and no degree
        tools.record_student_message(
            "I've worked in retail for five years and I don't have a bachelor's degree.",
            "typed",
        )

        with patch.object(tools, "_course_candidates", return_value=sample_courses):
            # Model incorrectly proposed professional_it_years=5
            res = tools.search_courses("cloud", has_bachelor_degree=False, professional_it_years=5)
            # Must guard to None (retail is not IT experience)
            self.assertIsNone(res["effective_professional_it_years"])
            self.assertIs(res["effective_has_bachelor_degree"], False)
            self.assertEqual(res["it_experience_status"]["source"], "unsupported")

            # Must NOT be marked met (retail does not satisfy 2+ years IT experience)
            # And because experience is unknown (None), it remains unknown, NOT excluded as unmet
            course = res["courses"][0]
            entry_check = next(c for c in course["suitability"]["checks"] if c["field"] == "entry_requirements")
            self.assertEqual(entry_check["status"], "unknown")

    def test_policy_and_negation_inquiries_do_not_satisfy_cloud_experience_route(self):
        from backend import tools

        sample_courses = [
            {
                "code": "GC-CC",
                "name": "Graduate Certificate in Cloud Computing",
                "faculty": "Engineering & Technology",
                "level": "Postgraduate",
                "study_mode": "Online",
                "duration_years": 0.5,
                "atar_cutoff": None,
                "entry_requirements": "Bachelor degree in IT/quantitative field, or 2+ years of professional IT experience",
                "annual_fee_aud": 12000,
                "career_outcomes": "Cloud architect.",
                "similarity": 0.85,
            },
        ]

        # Case A: Student asks policy question: "Does this require three years of IT experience?"
        tools.record_student_message("Does this require three years of IT experience?", "typed")
        with patch.object(tools, "_course_candidates", return_value=sample_courses):
            res = tools.search_courses("cloud", has_bachelor_degree=False, professional_it_years=3)
            self.assertIsNone(res["effective_professional_it_years"])
            self.assertEqual(res["it_experience_status"]["source"], "unsupported")
            # Must NOT be marked met! Stays unknown.
            course = res["courses"][0]
            entry_check = next(c for c in course["suitability"]["checks"] if c["field"] == "entry_requirements")
            self.assertEqual(entry_check["status"], "unknown")

        # Case B: Student states negated duration: "I do not have three years of IT experience."
        tools.record_student_message("I do not have three years of IT experience.", "typed")
        with patch.object(tools, "_course_candidates", return_value=sample_courses):
            res = tools.search_courses("cloud", has_bachelor_degree=False, professional_it_years=3)
            self.assertIsNone(res["effective_professional_it_years"])
            self.assertEqual(res["it_experience_status"]["source"], "unsupported")
            # Must NOT be marked met! Stays unknown.
            course = res["courses"][0]
            entry_check = next(c for c in course["suitability"]["checks"] if c["field"] == "entry_requirements")
            self.assertEqual(entry_check["status"], "unknown")

        # Case C: recommend_courses also enforces identical guard
        tools.record_student_message("Does this require three years of IT experience?", "typed")
        with patch.object(tools, "_course_candidates", return_value=sample_courses):
            res = tools.recommend_courses("cloud", "problem solving", has_bachelor_degree=False, professional_it_years=3)
            self.assertIsNone(res["effective_professional_it_years"])
            self.assertEqual(res["it_experience_status"]["source"], "unsupported")
            course = res["courses"][0]
            entry_check = next(c for c in course["suitability"]["checks"] if c["field"] == "entry_requirements")
            self.assertEqual(entry_check["status"], "unknown")


if __name__ == "__main__":
    unittest.main()
