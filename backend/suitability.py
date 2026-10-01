"""Conservative checks against explicit synthetic course facts, not admissions decisions."""

# Exact source statements: changed/unmapped prose is unknown, never regex-inferred.
DEGREE_REQUIRED = {
    'Bachelor degree in quantitative field with credit average (GPA 5.0/7.0) or above',
    'Bachelor degree in any discipline + minimum 3 years of professional work experience',
    'Approved 4-year teaching qualification, or degree + teaching postgrad, plus current teacher registration',
    'Relevant bachelor degree (completed within 10 years, GPA 5.0+), personal statement, and interview',
}
CLOUD_ENTRY = 'Bachelor degree in IT/quantitative field, or 2+ years of professional IT experience'


def assess(course, study_mode=None, target_level=None, has_bachelor_degree=None,
           professional_it_years=None, rejected_courses=None):
    checks = []
    def add(field, status, reason):
        checks.append({'field': field, 'status': status, 'reason': reason})
    if rejected_courses and (course.get('name') in rejected_courses or course.get('id') in rejected_courses):
        add('preference', 'unmet', f"Course '{course.get('name')}' was previously rejected by the student.")
    if study_mode:
        actual = course.get('study_mode')
        # Compare the stated catalogue label; never derive campus attendance from load.
        status = 'met' if actual and study_mode.lower() in actual.lower() else 'unknown'
        if study_mode.lower() == 'online' and actual and 'online' not in actual.lower():
            status = 'unmet'
        add('study_mode', status, f"Requested {study_mode}; catalogue label: {actual}. Attendance details not verified.")
    if target_level:
        actual = course.get('level')
        add('level', 'met' if actual and actual.casefold() == target_level.casefold() else 'unmet' if actual and target_level.casefold() in ('undergraduate', 'postgraduate') else 'unknown',
            f'Requested {target_level}; catalogue level: {actual}.')
    entry = course.get('entry_requirements')
    status = 'unknown'
    if entry in DEGREE_REQUIRED and has_bachelor_degree is False:
        status = 'unmet'
    elif entry == CLOUD_ENTRY:
        if professional_it_years is not None and professional_it_years >= 2:
            status = 'met'
        elif has_bachelor_degree is False and professional_it_years is not None:
            status = 'unmet'
    add('entry_requirements', status, entry or 'Entry requirements are not recorded; eligibility is not verified.')
    return {'status': 'unmet' if any(c['status']=='unmet' for c in checks) else 'unknown' if any(c['status']=='unknown' for c in checks) else 'met',
            'checks': checks, 'basis': 'self-reported context and catalogue facts; not an admission decision'}


def prepare(courses, limit, **context):
    candidates, excluded = [], []
    for course in courses:
        course = dict(course)
        course['suitability'] = assess(course, **context)
        if course['suitability']['status'] == 'unmet':
            excluded.append(course)
        else:
            candidates.append(course)
    return candidates[:limit], excluded
