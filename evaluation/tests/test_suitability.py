import unittest
from backend.suitability import assess, prepare, CLOUD_ENTRY

class SuitabilityTests(unittest.TestCase):
    def course(self, **kw):
        d = dict(name='Cloud', level='Postgraduate', study_mode='Online', entry_requirements=CLOUD_ENTRY)
        d.update(kw)
        return d
    def test_explicitly_unqualified_excluded(self):
        candidates, excluded = prepare([self.course()],4,has_bachelor_degree=False,professional_it_years=0)
        self.assertEqual(candidates,[])
        self.assertEqual(excluded[0]['suitability']['status'],'unmet')
    def test_experience_route_not_blanket_postgraduate_exclusion(self):
        result=assess(self.course(),has_bachelor_degree=False,professional_it_years=3)
        self.assertEqual(result['status'],'met')
    def test_unknown_alternative_route_stays_unknown(self):
        self.assertEqual(assess(self.course(),has_bachelor_degree=False)['status'],'unknown')
    def test_missing_requirements_not_eligible(self):
        c=self.course();c['entry_requirements']=None
        self.assertEqual(assess(c)['status'],'unknown')
    def test_online_correction_rejects_nononline_catalogue(self):
        c=self.course();c['study_mode']='Full-time'
        self.assertEqual(assess(c,study_mode='Online')['status'],'unmet')
    def test_changed_prose_not_interpreted_as_known_rule(self):
        c=self.course();c['entry_requirements']='Consult faculty about admission.'
        self.assertEqual(assess(c,has_bachelor_degree=False,professional_it_years=0)['status'],'unknown')
    def test_filter_before_limit(self):
        c=self.course();c['level']='Undergraduate';c['entry_requirements']=None
        candidates,_=prepare([self.course(),c],1,target_level='Undergraduate')
        self.assertEqual(candidates[0]['level'],'Undergraduate')

    def test_level_comparison_ignores_case(self):
        c=self.course();c['level']='Undergraduate';c['entry_requirements']=None
        self.assertEqual(assess(c,target_level='undergraduate')['status'],'unknown')
    def test_unknown_level_label_is_not_a_known_mismatch(self):
        self.assertEqual(assess(self.course(),target_level='degree')['status'],'unknown')

    def test_experience_correction_reassesses_from_met_to_unmet(self):
        # Initial disclosure: 3 years IT support -> Cloud Computing met
        initial = assess(self.course(), has_bachelor_degree=False, professional_it_years=3)
        self.assertEqual(initial['status'], 'met')
        # Corrected disclosure: 1 year IT support + 2 years coursework -> Cloud Computing unmet
        corrected = assess(self.course(), has_bachelor_degree=False, professional_it_years=1)
        self.assertEqual(corrected['status'], 'unmet')
        _, excluded = prepare([self.course()], 4, has_bachelor_degree=False, professional_it_years=1)
        self.assertEqual(len(excluded), 1)
        self.assertEqual(excluded[0]['suitability']['status'], 'unmet')

    def test_full_time_study_mode_does_not_assert_on_campus_attendance(self):
        c = self.course(study_mode='Full-time')
        res = assess(c, study_mode='Online')
        self.assertEqual(res['status'], 'unmet')
        # Full-time catalogue label does not prove campus attendance; note explicitly records attendance unverified
        self.assertIn("Attendance details not verified", res['checks'][0]['reason'])

    def test_postgraduate_scope_focused_vs_unconstrained_alternatives(self):
        undergrad = self.course(name='Bachelor of CS', level='Undergraduate', entry_requirements=None)
        # When focused on postgraduate scope
        candidates_focused, excluded_focused = prepare([self.course(), undergrad], 5, target_level='Postgraduate')
        self.assertEqual([c['name'] for c in candidates_focused], ['Cloud'])
        self.assertEqual([c['name'] for c in excluded_focused], ['Bachelor of CS'])
        # When exploring alternatives without target_level constraint
        candidates_open, excluded_open = prepare([self.course(), undergrad], 5)
        self.assertEqual([c['name'] for c in candidates_open], ['Cloud', 'Bachelor of CS'])
        self.assertEqual(excluded_open, [])

    def test_online_undergraduate_alternative_permitted_when_no_level_constraint(self):
        # Online student with no bachelor degree exploring alternatives without postgraduate restriction
        undergrad_online = self.course(name='Bachelor of CS', level='Undergraduate', study_mode='Online', entry_requirements=None)
        res = assess(undergrad_online, study_mode='Online', has_bachelor_degree=False)
        # Undergraduate study itself does NOT violate online preference
        mode_check = next(c for c in res['checks'] if c['field'] == 'study_mode')
        self.assertEqual(mode_check['status'], 'met')
        # Overall status is unknown because entry requirements are unrecorded, but NOT unmet
        self.assertNotEqual(res['status'], 'unmet')
        candidates, excluded = prepare([undergrad_online], 5, study_mode='Online', has_bachelor_degree=False)
        self.assertEqual([c['name'] for c in candidates], ['Bachelor of CS'])
        self.assertEqual(excluded, [])

    def test_on_campus_course_violates_online_delivery_constraint(self):
        # Course offered strictly on campus violates student's online-only preference
        on_campus = self.course(name='Bachelor of IT', study_mode='On-campus')
        res = assess(on_campus, study_mode='Online')
        self.assertEqual(res['status'], 'unmet')
        mode_check = next(c for c in res['checks'] if c['field'] == 'study_mode')
        self.assertEqual(mode_check['status'], 'unmet')
        _, excluded = prepare([on_campus], 5, study_mode='Online')
        self.assertEqual(len(excluded), 1)
        self.assertEqual(excluded[0]['name'], 'Bachelor of IT')

    def test_previously_rejected_alternative_excluded_from_recommendations(self):
        # If the student previously declined an alternative, it must not be re-offered
        rejected_course = self.course(name='Diploma of IT', study_mode='Online')
        res = assess(rejected_course, study_mode='Online', rejected_courses=['Diploma of IT'])
        self.assertEqual(res['status'], 'unmet')
        pref_check = next(c for c in res['checks'] if c['field'] == 'preference')
        self.assertEqual(pref_check['status'], 'unmet')
        self.assertIn("previously rejected", pref_check['reason'])
        candidates, excluded = prepare([rejected_course], 5, study_mode='Online', rejected_courses=['Diploma of IT'])
        self.assertEqual(candidates, [])
        self.assertEqual(len(excluded), 1)
        self.assertEqual(excluded[0]['name'], 'Diploma of IT')
