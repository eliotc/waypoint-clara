"""Date-neutral event text and rolling schedules for synthetic local evaluations."""
from datetime import datetime, timedelta
import re
from zoneinfo import ZoneInfo

ZONE = ZoneInfo('Australia/Melbourne')
CALENDAR_PREFIX = re.compile(r'^(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|January|February|March|April|May|June|July|August|September|October|November|December) Campus Tour$')
# Explicitly replace temporal claims instead of fabricating new admissions deadlines.
OVERRIDES = {
    'Kingsford Open Day 2026': ('Kingsford Open Day', None),
    'Scholarship & Financial Aid Webinar': (None, 'Learn about merit scholarships, equity bursaries, and the application process. Our Financial Aid team will explain HECS-HELP eligibility, payment plans, and how to apply.'),
    'Mid-Year Admissions Webinar': ('Admissions Webinar', 'Information session on applications, credit transfers, and how to find the applicable deadlines for domestic and international students.'),
    'Mid-Year Enrolment Webinar': ('Enrolment Webinar', 'Learn about available programs, credit transfer applications, and how to submit a direct application for postgraduate courses.'),
    'VTAC Application Workshop': (None, 'Step-by-step walkthrough of the VTAC application process. Covers course selection, preference order, special entry access schemes, and how to find applicable deadlines.'),
    'Scholarship Application Info Night': (None, 'Meet the Financial Aid team and learn how to submit a strong scholarship application. Covers merit, equity, faculty, and international scholarships.'),
    'International Student Info Session': (None, 'For prospective international students. Covers visa requirements, English language pathways, tuition fees, scholarships, and on-campus housing. Presented in English with Mandarin and Hindi support available.'),
    'Late VTAC Applications Closing — Info Webinar': ('VTAC Applications Info Webinar', 'Information session covering preference changes, direct postgraduate applications, and what to expect when offers are released.'),
    'Year-End Info Evening — What Happens Next': ('School-to-University Info Evening', 'For prospective students: how to read an offer letter, enrolment steps, orientation, and how to prepare for university life at Kingsford.'),
    'Pre-Offer Information Session': ('Offer Information Session', 'Covers what to do when you receive an offer, how to accept, enrolment steps, HECS-HELP setup, and orientation.'),
    'December Campus Tour': ('Campus Tour', 'Guided walk of the main campus for prospective students and families.'),
    'International Pre-Departure Orientation': (None, 'For international students who have accepted an offer. Covers what to bring, arrival procedures, temporary housing, bank account setup, SIM cards, and connecting with the Kingsford Peer Mentor program before you land.'),
    'Summer School Info Webinar': ('Accelerated Study Info Webinar', 'Explore accelerated study options, making up units, and getting a head start on first-year subjects. Open to incoming and continuing students.'),
}


def rebase_event(event_id, title, description, start, end, anchor):
    new_title, new_description = OVERRIDES.get(title, (None, None))
    title = new_title or ('Campus Tour' if CALENDAR_PREFIX.fullmatch(title) else title)
    description = new_description or description
    local_start = start.astimezone(ZONE)
    day = anchor.astimezone(ZONE).date() + timedelta(days=event_id + 7)
    rebased = datetime.combine(day, local_start.timetz(), tzinfo=ZONE)
    # Arithmetic in UTC preserves elapsed duration across daylight-saving changes.
    from datetime import timezone
    finish = rebased.astimezone(timezone.utc) + (end - start)
    return title, description, rebased, finish


def rebase_events(cur):
    cur.execute('SELECT CURRENT_TIMESTAMP')
    anchor = cur.fetchone()[0]
    cur.execute('SELECT id, title, description, start_at, end_at FROM events ORDER BY id')
    for event_id, title, description, start, end in cur.fetchall():
        values = rebase_event(event_id, title, description, start, end, anchor)
        cur.execute('UPDATE events SET title=%s, description=%s, start_at=%s, end_at=%s WHERE id=%s', (*values, event_id))
    return anchor.isoformat()
