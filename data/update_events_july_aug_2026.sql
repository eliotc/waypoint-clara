-- Event date refresh: shift all events to July–August 2026
-- Run directly in Cloud SQL Studio against the `waypoint` database.
-- Safe to re-run: all statements are idempotent (UPDATE by title).
--
-- Background: search_events defaults to a 30-day window from today.
-- Events must be kept in the future or Clara will report "no events coming up."
-- Next refresh needed: around late June 2026 (before Jul 11 events pass).
--
-- How to run:
--   Cloud SQL Studio → connect to `waypoint` DB as `waypoint_user`
--   Paste and execute this file.
--   Verify with: SELECT title, start_at FROM events ORDER BY start_at;

UPDATE events SET
    start_at = '2026-07-11 10:00+10', end_at = '2026-07-11 11:30+10'
WHERE title = 'Saturday Campus Tour'
  AND start_at = (SELECT MIN(start_at) FROM events WHERE title = 'Saturday Campus Tour');

UPDATE events SET
    start_at = '2026-07-25 10:00+10', end_at = '2026-07-25 11:30+10'
WHERE title = 'Saturday Campus Tour'
  AND start_at = (SELECT MAX(start_at) FROM events WHERE title = 'Saturday Campus Tour');

UPDATE events SET
    start_at = '2026-07-14 12:00+10', end_at = '2026-07-14 13:00+10'
WHERE title = 'Scholarship & Financial Aid Webinar';

UPDATE events SET
    start_at = '2026-07-16 18:00+10', end_at = '2026-07-16 19:30+10'
WHERE title = 'Engineering & Tech Info Session';

UPDATE events SET
    start_at = '2026-07-18 09:00+10', end_at = '2026-07-18 16:00+10'
WHERE title = 'Kingsford Open Day 2026';

UPDATE events SET
    start_at = '2026-07-19 10:00+10', end_at = '2026-07-19 11:30+10'
WHERE title = 'Health Sciences Campus Tour';

UPDATE events SET
    start_at = '2026-07-22 18:00+10', end_at = '2026-07-22 20:00+10'
WHERE title = 'Postgrad Open Evening';

UPDATE events SET
    start_at = '2026-07-23 17:30+10', end_at = '2026-07-23 19:00+10'
WHERE title = 'Business & Commerce Info Night';

UPDATE events SET
    start_at = '2026-08-01 14:00+10', end_at = '2026-08-01 16:00+10'
WHERE title = 'Arts & Humanities Open Studio';

UPDATE events SET
    start_at = '2026-08-05 10:00+10', end_at = '2026-08-05 12:00+10'
WHERE title = 'International Students Welcome Session';

-- Verify
SELECT title, start_at::date AS date, spots_left FROM events ORDER BY start_at;
