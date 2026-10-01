"""Contract tests for source-bound experience and eligibility, including unseen variants."""
import asyncio
import unittest
from unittest.mock import patch
from backend.experience_status import resolve_it_experience

CASES = [
    (["I am interested in IT; three years were professional retail work."], None),
    (["I have one year of professional IT experience.", "I worked in retail for five years; three years were professional."], 1.0),
    (["I have one year of professional IT experience.", "My sister worked in nursing; three years were professional."], 1.0),
    (["I have one year of professional IT experience; my sister worked in nursing; three years were professional."], 1.0),
    (["I have one year of professional IT experience. Three years were professional."], None),
    (["I have three years of IT experience, but only some were professional."], None),
    (["I have three years of IT experience, but only one year was professional; the rest was coursework."], None),
    (["I have one year of professional IT experience, but three years were professional."], None),
    (["I've got 2.5 years working in cloud computing. Does that count?"], 2.5),
    (["I’ve got 2.5 years working in cloud computing!"], 2.5),
    (["I have no IT experience. My sister has three years in IT."], 0.0),
    (["I have three years in IT?"], None),
    (["The example reads: I have three years in IT."], None),
    (["I have three years in IT.", "Actually, I do not have three years of IT experience."], None),
    (["I don't have IT qualifications."], None),
    (["I don't have IT certifications."], None),
    (["I have three years of IT experience, all of it coursework."], None),
    (["I have three years of IT experience, mostly personal projects."], None),
    (["I have three years of IT experience, none of it in a professional workplace."], None),
    (["I have four years of IT experience, all of it academic study."], None),
    (["I have three years of IT experience.", "Only one year was professional; the rest was coursework."], None),
    (["I have three years of IT experience.", "Actually, none of it was professional."], None),
    (["I have three years of professional IT experience.", "Only online courses, please."], 3.0),
    (["I have three years of IT experience.", "Only one year was professional. Actually, I have two years of professional IT experience."], 2.0),
    (["I have three years of IT experience. Only one year was professional; the rest was coursework."], None),
    (["I have three years of IT experience from university coursework."], None),
    (["I have three years of IT experience."], None),
    (["I have two years of experience in technical support."], None),
    (["I have three years in IT."], None),
    (["I have three years of professional IT experience.", "Only one year was professional."], None),
    (["I have three years of professional IT experience.", "I worked in IT for one year."], 1.0),
    (["I have three years of professional IT experience.", "I have no IT experience."], 0.0),
    (["I have three years of professional IT experience.", "Actually, that experience was all coursework."], None),
    (["I have three years of professional IT experience.", "My coursework was in physics."], 3.0),
    (["I have three years of professional IT experience.", "My sister worked in IT. That experience was all coursework."], 3.0),
    (["I have three years of professional IT experience.", "That was university employment, not coursework."], 3.0),
    (["I have three years of professional IT experience.", "My sister works in IT. My experience was all coursework."], None),
    (["I have three years of professional IT experience.", "My experience was all coursework. My sister works in IT."], None),
    (["I have three years of professional IT experience.", "That experience was all coursework, not paid work."], None),
    (["I have three years of professional IT experience.", "My experience was all coursework; my sister worked in retail."], None),
    (["I have three years of professional IT experience.", "My experience was all coursework, but my sister has a job in retail."], None),
    (["If I move to Melbourne and I have three years of professional IT experience."], None),
    (["I have three years of IT experience.", "I worked in IT support professionally for three years."], 3.0),
    (["I have three years of IT experience.", "I worked professionally in IT support for three years."], 3.0),
    (["I have three years of IT experience.", "I have three years of full-time IT experience."], 3.0),
]

class BindingTests(unittest.TestCase):
    def test_boundary_matrix(self):
        for messages, expected in CASES:
            with self.subTest(messages=messages):
                result = resolve_it_experience([{'id': i+1, 'text': s} for i,s in enumerate(messages)], proposed=9)
                self.assertEqual(result['effective'], expected)
                self.assertEqual(result['proposed'], 9)

    def test_partial_refinement_requests_clarification(self):
        result = resolve_it_experience([{'id': 7, 'text': CASES[6][0][0]}])
        self.assertIsNone(result['evidence'])
        self.assertTrue(result['needs_clarification'])
        self.assertEqual(result['unresolved_evidence']['message_id'], 7)


class ToolBindingTests(unittest.IsolatedAsyncioTestCase):
    async def test_both_tools_cannot_upgrade_unrelated_experience(self):
        from backend import tools
        from backend.suitability import CLOUD_ENTRY
        async def sink(payload): pass
        course = dict(code='TEST', name='Graduate Certificate in Cloud Computing',
                      faculty='Engineering', level='Postgraduate', study_mode='Online',
                      atar_cutoff=None, entry_requirements=CLOUD_ENTRY, description='Test',
                      duration_years=.5, annual_fee_aud=8000, career_outcomes='Test', similarity=.9)
        for tool in [tools.search_courses, tools.recommend_courses]:
            for index, (messages, expected) in enumerate(CASES):
                with self.subTest(tool=tool.__name__, messages=messages):
                    sid=f'bound-{tool.__name__}-{index}'
                    tools.register_display_callback(sid, asyncio.get_running_loop(), sink)
                    token=tools.bind_display_session(sid)
                    try:
                        tools.record_student_message("I don't have a bachelor's degree.", 'typed')
                        for text in messages: tools.record_student_message(text, 'typed')
                        args=('cloud',) if tool is tools.search_courses else ('cloud','problem solving')
                        with patch.object(tools, '_course_candidates', return_value=[course]):
                            result=tool(*args, has_bachelor_degree=False, professional_it_years=9)
                        self.assertEqual(result['effective_professional_it_years'], expected)
                        self.assertEqual(result['proposed_professional_it_years'], 9)
                        self.assertEqual(result['it_experience_status']['needs_clarification'], expected is None)
                        self.assertEqual(bool(result['it_experience_status']['clarification_question']), expected is None)
                        candidates=result['courses'] + result.get('excluded_examples', [])
                        check=next(c for c in candidates[0]['suitability']['checks'] if c['field']=='entry_requirements')
                        self.assertEqual(check['status'], 'unknown' if expected is None else 'met' if expected>=2 else 'unmet')
                    finally:
                        tools.reset_display_session(token)
                        tools.unregister_display_callback(sid)
