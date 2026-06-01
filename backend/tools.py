"""
Waypoint ADK tools.
All tools must be synchronous (ADK calls them in a thread pool).
"""
import asyncio
import logging
import os
from datetime import date
from typing import Any, Callable, Coroutine, Optional

import google.genai as genai
import google.genai.types as genai_types

_genai_client: genai.Client | None = None
log = logging.getLogger(__name__)

def _get_genai_client() -> genai.Client:
    global _genai_client
    if _genai_client is None:
        # Fallback to ADC (Vertex AI) if API key is not in env
        _genai_client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))
    return _genai_client

# ── display_data side-channel ─────────────────────────────────────────────────
# Day 4 WebSocket bridge registers an async callback here per session.
# display_data calls it via run_coroutine_threadsafe so the frontend gets cards
# without waiting for the model to finish speaking.

_display_callbacks: dict[str, tuple[asyncio.AbstractEventLoop, Callable]] = {}


def register_display_callback(
    session_id: str,
    loop: asyncio.AbstractEventLoop,
    callback: Callable[[dict], Coroutine],
) -> None:
    _display_callbacks[session_id] = (loop, callback)


def unregister_display_callback(session_id: str) -> None:
    _display_callbacks.pop(session_id, None)

# ── Embedding helper ──────────────────────────────────────────────────────────

from functools import lru_cache

@lru_cache(maxsize=64)
def _embed(text: str) -> tuple[float, ...]:
    """Embed text via Gemini. Results are LRU-cached to avoid repeated API calls."""
    result = _get_genai_client().models.embed_content(
        model="gemini-embedding-001",
        contents=[text],
        config=genai_types.EmbedContentConfig(output_dimensionality=1536),
    )
    return tuple(result.embeddings[0].values)


def _emb_str(values) -> str:
    return "[" + ",".join(str(v) for v in values) + "]"


def _to_json_safe(row: dict) -> dict:
    """Convert psycopg2 row to JSON-safe Python primitives.

    NUMERIC(3,1) maps to Decimal, which json.dumps can't handle.
    Also truncates long text fields to keep function responses small.
    """
    from decimal import Decimal
    result = {}
    for k, v in row.items():
        if isinstance(v, Decimal):
            result[k] = float(v)
        elif isinstance(v, str) and k == "description" and len(v) > 300:
            result[k] = v[:300] + "…"
        else:
            result[k] = v
    return result


# ── DB helper (sync via asyncpg run_until_complete workaround) ────────────────
# Tools run in a thread; we use a fresh psycopg2 connection per call
# to stay fully synchronous without event-loop gymnastics.

import psycopg2
import psycopg2.extras
import psycopg2.pool

_pg_pool: psycopg2.pool.ThreadedConnectionPool | None = None

def _get_pg_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pg_pool
    if _pg_pool is None:
        _pg_pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1, maxconn=5, dsn=os.environ["DATABASE_URL"]
        )
    return _pg_pool

from contextlib import contextmanager

@contextmanager
def _get_conn():
    pool = _get_pg_pool()
    conn = None
    try:
        conn = pool.getconn()
        # Basic validation: check if connection is still alive
        # poll() returns None if everything is okay
        try:
            conn.poll()
        except (psycopg2.OperationalError, psycopg2.InterfaceError):
            log.warning("Database connection stale, attempting to refresh...")
            pool.putconn(conn, close=True)
            conn = pool.getconn()

        conn.autocommit = True
        yield conn
    except Exception as e:
        log.error("Database connection error: %s", e)
        raise
    finally:
        if conn:
            pool.putconn(conn)


# ── Tool 1: get_course_detail ─────────────────────────────────────────────────

def get_course_detail(course_name: str) -> dict:
    """
    Get full details for a specific Kingsford University course by name.
    Call this when a student asks for more information about a particular course
    they have already seen or heard about (e.g. 'tell me more about Master of Data Science').
    Returns complete course info including full description, career outcomes, fees, and ATAR.
    """
    log.debug("get_course_detail course_name='%s'", course_name)
    emb = _emb_str(_embed(course_name))
    sql = """
        SELECT code, name, faculty, level, study_mode,
               duration_years, atar_cutoff, entry_requirements, annual_fee_aud,
               description, career_outcomes,
               1 - (embedding <=> %s::vector) AS similarity
        FROM courses
        ORDER BY embedding <=> %s::vector
        LIMIT 1
    """
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (emb, emb))
            row = cur.fetchone()

    if not row:
        return {"found": False, "message": f"No course found matching '{course_name}'."}

    from decimal import Decimal
    course = {}
    for k, v in dict(row).items():
        course[k] = float(v) if isinstance(v, Decimal) else v

    log.info("get_course_detail found '%s' (similarity=%.3f)", course["name"], course["similarity"])

    if _display_callbacks:
        payload = {
            "type": "card",
            "card_type": "course_detail",
            "data": course,
            "spoken_summary": f"Here are the full details for {course['name']}.",
        }
        for loop, callback in _display_callbacks.values():
            asyncio.run_coroutine_threadsafe(callback(payload), loop)

    return {
        "name": course["name"],
        "faculty": course["faculty"],
        "level": course["level"],
        "study_mode": course["study_mode"],
        "duration_years": course["duration_years"],
        "atar_cutoff": course["atar_cutoff"],
        "entry_requirements": course.get("entry_requirements"),
        "annual_fee_aud": course["annual_fee_aud"],
        "career_outcomes": course["career_outcomes"],
    }


# ── Tool 1b: compare_courses ──────────────────────────────────────────────────

def compare_courses(course_name_a: str, course_name_b: str) -> dict:
    """
    Compare two specific Kingsford University courses side by side.
    Call this when a student wants to weigh two named courses against each other
    (e.g. 'how does Computer Science compare to Software Engineering?').
    Renders a side-by-side comparison card covering faculty, level, study mode,
    duration, annual fee, entry requirements, and career outcomes for both courses.
    """
    log.debug("compare_courses a='%s' b='%s'", course_name_a, course_name_b)
    sql = """
        SELECT code, name, faculty, level, study_mode,
               duration_years, atar_cutoff, entry_requirements, annual_fee_aud,
               description, career_outcomes
        FROM courses
        ORDER BY embedding <=> %s::vector
        LIMIT 1
    """
    courses = []
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            for name in (course_name_a, course_name_b):
                cur.execute(sql, (_emb_str(_embed(name)),))
                row = cur.fetchone()
                if row:
                    courses.append(_to_json_safe(dict(row)))

    if len(courses) < 2:
        return {
            "found": False,
            "message": "I couldn't find two courses to compare. Please name both courses clearly.",
        }

    if courses[0]["code"] == courses[1]["code"]:
        return {
            "found": False,
            "message": (
                f"Both names matched the same course ({courses[0]['name']}). "
                "Please name two different courses to compare."
            ),
        }

    log.info("compare_courses comparing '%s' vs '%s'", courses[0]["name"], courses[1]["name"])

    if _display_callbacks:
        payload = {
            "type": "card",
            "card_type": "comparison",
            "data": {"courses": courses},
            "spoken_summary": (
                f"Here's how {courses[0]['name']} and {courses[1]['name']} compare."
            ),
        }
        for loop, callback in _display_callbacks.values():
            asyncio.run_coroutine_threadsafe(callback(payload), loop)

    # Compact, structured summary for the model — full data is already on the card.
    return {
        "comparing": [c["name"] for c in courses],
        "courses": [
            {
                "name": c["name"],
                "faculty": c["faculty"],
                "level": c["level"],
                "study_mode": c["study_mode"],
                "duration_years": c["duration_years"],
                "atar_cutoff": c["atar_cutoff"],
                "entry_requirements": c.get("entry_requirements"),
                "annual_fee_aud": c["annual_fee_aud"],
            }
            for c in courses
        ],
    }


# ── Tool 2: search_courses ────────────────────────────────────────────────────

def search_courses(
    query: str,
    faculty: Optional[str] = None,
    student_atar: Optional[int] = None,
) -> dict:
    """
    Search Kingsford University courses by a natural-language query.
    Optionally filter by faculty (e.g. 'Engineering & Technology', 'Business & Commerce',
    'Arts & Humanities', 'Health Sciences').
    Optionally filter by a student's ATAR cutoff to exclude courses above their score.
    Returns up to 5 matching courses with key details.
    """
    log.debug("search_courses query='%s' faculty=%s student_atar=%s", query, faculty, student_atar)
    emb = _emb_str(_embed(query))
    log.debug("Embedding generated, executing SQL...")

    atar_filter = ""
    params = [emb, faculty, f"%{faculty}%" if faculty else None]

    if student_atar is not None:
        try:
            atar_val = int(student_atar)
            atar_filter = "AND (atar_cutoff IS NULL OR atar_cutoff <= %s)"
            params.append(atar_val)
        except (ValueError, TypeError):
            pass

    params.append(emb)

    sql = f"""
        SELECT code, name, faculty, level, study_mode,
               duration_years, atar_cutoff, entry_requirements, annual_fee_aud,
               career_outcomes,
               1 - (embedding <=> %s::vector) AS similarity
        FROM courses
        WHERE (%s::text IS NULL OR faculty ILIKE %s) {atar_filter}
        ORDER BY embedding <=> %s::vector
        LIMIT 5
    """
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    courses = [_to_json_safe(dict(r)) for r in rows]
    log.info("search_courses found %d results for '%s'", len(courses), query)

    # Send full data directly to browser (bypasses model entirely)
    if _display_callbacks:
        payload = {"type": "card", "card_type": "courses", "data": {"courses": courses, "count": len(courses)}, "spoken_summary": "Here are some matching courses."}
        for loop, callback in _display_callbacks.values():
            asyncio.run_coroutine_threadsafe(callback(payload), loop)

    # Return minimal summary to model — full data already on the card.
    # Keeping the response small reduces 1008 crashes with native audio.
    names = [c["name"] for c in courses[:3]]
    return {"count": len(courses), "top_courses": names}


# ── Tool 2: search_events ────────────────────────────────────────────────────

def search_events(event_type: Optional[str] = None, date_range: Optional[str] = None) -> dict:
    """
    Search upcoming Kingsford University events.
    event_type: one of OpenDay, InfoSession, CampusTour, Webinar (or None for all).
    date_range: optional ISO date range like '2026-03-10,2026-03-20' (or None for next 30 days).
    Returns matching events with title, type, date, location, and spots remaining.
    """
    from datetime import datetime, timedelta, timezone

    now = datetime.now(tz=timezone.utc)
    if date_range:
        parts = date_range.split(",")
        date_from = parts[0].strip()
        date_to   = parts[1].strip() if len(parts) > 1 else (now + timedelta(days=90)).date().isoformat()
    else:
        date_from = now.date().isoformat()
        date_to   = (now + timedelta(days=90)).date().isoformat()

    sql = """
        SELECT id, title, event_type, start_at, end_at, location,
               description, spots_left
        FROM events
        WHERE (%s::text IS NULL OR event_type ILIKE %s)
          AND start_at >= %s::date
          AND start_at <  %s::date + INTERVAL '1 day'
        ORDER BY start_at
        LIMIT 10
    """
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (
                event_type, f"%{event_type}%" if event_type else None,
                date_from, date_to,
            ))
            rows = cur.fetchall()

    events = []
    for r in rows:
        d = dict(r)
        d["start_at"] = d["start_at"].isoformat() if d["start_at"] else None
        d["end_at"]   = d["end_at"].isoformat()   if d["end_at"]   else None
        events.append(d)
    log.info("search_events found %d results (type=%s)", len(events), event_type)

    # Send full data directly to browser
    if _display_callbacks:
        payload = {"type": "card", "card_type": "events", "data": {"events": events, "count": len(events)}, "spoken_summary": "Here are some upcoming events."}
        for loop, callback in _display_callbacks.values():
            asyncio.run_coroutine_threadsafe(callback(payload), loop)

    # Return a descriptive summary to the model
    summary = []
    for e in events[:5]:
        summary.append({
            "title": e["title"],
            "start_at": e["start_at"],
            "location": e["location"],
            "description": e["description"][:150] + "..." if e["description"] else ""
        })
    return {"count": len(events), "events": summary}


# ── Similarity Scaling Helper ──────────────────────────────────────────────────

def _scale_similarity(similarity: float) -> int:
    """
    Scale realistic 0.30 - 0.65 cosine similarity band to user-friendly 60% - 99% range.
    Ensures that reasonably strong matches don't display discouraged low numbers.
    """
    if similarity < 0.30:
        val = 50 + (similarity / 0.30) * 10
    else:
        val = 60 + ((similarity - 0.30) / (0.65 - 0.30)) * 40
    return min(100, max(0, round(val)))


# ── Tool 3: recommend_courses ─────────────────────────────────────────────────

def recommend_courses(
    interests: str,
    strengths: str,
    study_mode_preference: Optional[str] = None,
    student_atar: Optional[int] = None,
) -> dict:
    """
    Recommend Kingsford University courses tailored to a student's interests,
    strengths, and preferred study mode.
    interests: free-text description of what the student enjoys (e.g. 'maths, problem solving').
    strengths: free-text description of their academic strengths (e.g. 'sciences, writing').
    study_mode_preference: 'Full-time', 'Part-time', 'Online', or None for any.
    student_atar: optionally filter by student's ATAR score to exclude courses requiring higher scores.
    Returns up to 4 recommended courses with a match score and brief rationale.
    """
    query = f"student interested in {interests} with strengths in {strengths}"
    emb = _emb_str(_embed(query))

    mode_filter = ""
    atar_filter = ""
    params: list[Any] = [emb]
    if study_mode_preference:
        mode_filter = "AND study_mode ILIKE %s"
        params.append(f"%{study_mode_preference}%")

    if student_atar is not None:
        try:
            atar_val = int(student_atar)
            atar_filter = "AND (atar_cutoff IS NULL OR atar_cutoff <= %s)"
            params.append(atar_val)
        except (ValueError, TypeError):
            pass

    params.append(emb)

    sql = f"""
        SELECT code, name, faculty, level, study_mode,
               duration_years, atar_cutoff, entry_requirements, annual_fee_aud,
               career_outcomes,
               1 - (embedding <=> %s::vector) AS similarity
        FROM courses
        WHERE 1=1 {mode_filter} {atar_filter}
        ORDER BY embedding <=> %s::vector
        LIMIT 4
    """
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    results = []
    for r in rows:
        d = _to_json_safe(dict(r))
        d["match_pct"] = _scale_similarity(float(d["similarity"]))
        results.append(d)
    log.info("recommend_courses found %d results for '%s'", len(results), query)

    # Send full data directly to browser
    if _display_callbacks:
        payload = {"type": "card", "card_type": "courses", "data": {"courses": results, "count": len(results)}, "spoken_summary": "I recommend these courses based on your interests."}
        for loop, callback in _display_callbacks.values():
            asyncio.run_coroutine_threadsafe(callback(payload), loop)

    # Return minimal summary to model
    names = [r["name"] for r in results[:3]]
    return {"count": len(results), "top_recommendations": names}


# ── Tool 4: book_campus_tour ──────────────────────────────────────────────────

def book_campus_tour(
    student_name: str,
    preferred_date: str,
    email: str = "",
    party_size: int = 1,
) -> dict:
    """
    Book a campus tour at Kingsford University.
    preferred_date: ISO date string, e.g. '2026-03-15'.
    email: optional — only include if the student has explicitly provided it. Do NOT guess or fabricate.
    party_size: number of people attending (including the student), max 6.
    Returns a booking confirmation with a reference ID.
    """
    if party_size < 1 or party_size > 6:
        return {"success": False, "error": "party_size must be between 1 and 6"}

    try:
        tour_date = date.fromisoformat(preferred_date)
    except ValueError:
        return {"success": False, "error": f"Invalid date format: {preferred_date}. Use YYYY-MM-DD."}

    if tour_date < date.today():
        return {"success": False, "error": f"The date {preferred_date} is in the past. Campus tours must be booked for a future date."}

    sql = """
        INSERT INTO tour_bookings (student_name, email, preferred_date, party_size)
        VALUES (%s, %s, %s, %s)
        RETURNING id, created_at
    """
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (student_name, email, tour_date, party_size))
            row = dict(cur.fetchone())

    data = {
        "success": True,
        "booking_id": f"GT-{row['id']:05d}",
        "student_name": student_name,
        "email": email,
        "preferred_date": preferred_date,
        "party_size": party_size,
        "message": (
            f"Tour booked! Your reference is GT-{row['id']:05d}. "
            + (f"A confirmation will be sent to {email}." if email else "")
        ),
    }

    if _display_callbacks:
        payload = {"type": "card", "card_type": "booking", "data": data, "spoken_summary": "Your tour is booked!"}
        for loop, callback in _display_callbacks.values():
            asyncio.run_coroutine_threadsafe(callback(payload), loop)

    return data


# ── Tool 4b: register_for_event ──────────────────────────────────────────────

def register_for_event(event_title: str, student_name: str, email: str) -> dict:
    """
    Register a student for a specific Kingsford University event.
    Call this when a student wants to attend an event AND has provided their
    full name and email address. Do NOT call this tool until you have both.
    event_title: the name of the event (matched by partial title search).
    student_name: the student's full name.
    email: the student's email address.
    Returns a confirmation reference in EV-XXXXX format.
    """
    log.debug("register_for_event event='%s' name='%s'", event_title, student_name)

    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT id, title, event_type, start_at, location, spots_left
                FROM events
                WHERE title ILIKE %s
                ORDER BY ABS(EXTRACT(EPOCH FROM (start_at - NOW()))) ASC
                LIMIT 1
            """, (f"%{event_title}%",))
            event = cur.fetchone()

            if not event:
                return {
                    "success": False,
                    "error": f"I couldn't find an event matching '{event_title}'. Please check the event name.",
                }

            if event["spots_left"] is not None and event["spots_left"] <= 0:
                return {
                    "success": False,
                    "error": f"Sorry, {event['title']} is fully booked. Would you like me to find other upcoming events?",
                }

            cur.execute("""
                INSERT INTO event_registrations (event_id, student_name, email)
                VALUES (%s, %s, %s)
                RETURNING id
            """, (event["id"], student_name, email))
            reg_id = cur.fetchone()["id"]
            ref = f"EV-{reg_id:05d}"

            if event["spots_left"] is not None:
                cur.execute(
                    "UPDATE events SET spots_left = GREATEST(0, spots_left - 1) WHERE id = %s",
                    (event["id"],)
                )
            conn.commit()

    event_date = ""
    if event.get("start_at"):
        dt = event["start_at"]
        if hasattr(dt, "strftime"):
            event_date = dt.strftime("%-d %B %Y, %-I:%M %p")

    log.info("register_for_event confirmed %s for '%s'", ref, event["title"])

    if _display_callbacks:
        payload = {
            "type": "card",
            "card_type": "event_registration",
            "data": {
                "confirmation_ref": ref,
                "event_title": event["title"],
                "event_type": event.get("event_type", ""),
                "event_date": event_date,
                "location": event.get("location", ""),
                "student_name": student_name,
                "email": email,
            },
            "spoken_summary": f"You're registered! Your confirmation reference is {ref}.",
        }
        for loop, callback in _display_callbacks.values():
            asyncio.run_coroutine_threadsafe(callback(payload), loop)

    return {
        "success": True,
        "confirmation_ref": ref,
        "event": event["title"],
        "student_name": student_name,
        "email": email,
    }


# ── Tool 5: search_knowledge ─────────────────────────────────────────────────

def search_knowledge(query: str, faculty: Optional[str] = None) -> dict:
    """
    Search Kingsford University's general knowledge base for information about
    admissions, fees, HECS-HELP, scholarships, campus life, facilities,
    international students, visa requirements, career outcomes, and more.
    Call this whenever a student asks a general question not covered by
    search_courses, search_events, or search_scholarships.
    faculty: optionally scope the search to a faculty (e.g. 'Engineering & Technology',
    'Business & Commerce', 'Health Sciences', 'Arts & Humanities'). Pass this for
    faculty-specific questions like career outcomes so results aren't dominated by
    another faculty's content.
    Returns the most relevant information chunks from the knowledge base.
    """
    log.debug("search_knowledge query='%s' faculty=%s", query, faculty)
    # Bias the embedding toward the faculty when one is supplied, so faculty-specific
    # questions (e.g. career outcomes) rank that faculty's content higher.
    emb = _emb_str(_embed(f"{query} (faculty: {faculty})" if faculty else query))
    # When a faculty is given, prefer chunks that explicitly mention it before falling
    # back to pure vector similarity. This keeps e.g. "Business careers" from surfacing
    # the Engineering career chunk just because its embedding is marginally closer.
    sql = """
        SELECT topic, title, content,
               1 - (embedding <=> %s::vector) AS similarity
        FROM knowledge_docs
        ORDER BY
            CASE WHEN %s::text IS NOT NULL AND content ILIKE %s THEN 0 ELSE 1 END,
            embedding <=> %s::vector
        LIMIT 3
    """
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (emb, faculty, f"%{faculty}%" if faculty else None, emb))
            rows = cur.fetchall()

    chunks = [dict(r) for r in rows]
    log.info("search_knowledge found %d chunks for '%s'", len(chunks), query)

    if _display_callbacks:
        payload = {
            "type": "card",
            "card_type": "info",
            "data": {"chunks": chunks, "query": query},
            "spoken_summary": "Here's some information that might help.",
        }
        for loop, callback in _display_callbacks.values():
            asyncio.run_coroutine_threadsafe(callback(payload), loop)

    # Return a compact summary to the model
    if chunks:
        top = chunks[0]
        return {
            "topic": top["topic"],
            "title": top["title"],
            "excerpt": top["content"][:500],
            "additional_sections": [c["title"] for c in chunks[1:]],
        }
    return {"found": False, "message": "No relevant information found in the knowledge base."}


# ── Tool 6: search_scholarships ───────────────────────────────────────────────

def search_scholarships(
    query: str,
    scholarship_type: Optional[str] = None,
) -> dict:
    """
    Search Kingsford University scholarships, bursaries, and awards.
    Use this when a student asks about financial support, scholarships, bursaries,
    awards, or how to reduce the cost of their degree.
    query: what the student is looking for (e.g. 'merit scholarship', 'international student funding').
    scholarship_type: optionally filter by type — 'Merit', 'Equity', 'International', or 'Faculty'.
    Returns matching scholarships with eligibility, value, and deadline.
    """
    log.debug("search_scholarships query='%s' type=%s", query, scholarship_type)
    emb = _emb_str(_embed(query))
    sql = """
        SELECT name, type, faculty, annual_value_aud, duration_years,
               eligibility, description, application_deadline,
               1 - (embedding <=> %s::vector) AS similarity
        FROM scholarships
        WHERE (%s::text IS NULL OR type ILIKE %s)
        ORDER BY embedding <=> %s::vector
        LIMIT 4
    """
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (
                emb,
                scholarship_type, f"%{scholarship_type}%" if scholarship_type else None,
                emb,
            ))
            rows = cur.fetchall()

    scholarships = []
    for r in rows:
        d = dict(r)
        if d.get("application_deadline"):
            d["application_deadline"] = d["application_deadline"].isoformat()
        scholarships.append(d)
    log.info("search_scholarships found %d results for '%s'", len(scholarships), query)

    if _display_callbacks:
        payload = {
            "type": "card",
            "card_type": "scholarships",
            "data": {"scholarships": scholarships, "count": len(scholarships)},
            "spoken_summary": "Here are some scholarships you might be eligible for.",
        }
        for loop, callback in _display_callbacks.values():
            asyncio.run_coroutine_threadsafe(callback(payload), loop)

    names = [s["name"] for s in scholarships[:3]]
    return {"count": len(scholarships), "top_scholarships": names}


# ── Tool 7: display_data ──────────────────────────────────────────────────────

def display_data(type: str, data: dict, spoken_summary: str) -> dict:
    """
    Send structured data to the student's browser as a visual card.
    Call this alongside every substantive spoken response so the UI shows details.
    type: 'courses', 'events', 'booking', 'info'.
    data: the structured payload to render (course list, event list, booking confirmation, etc.).
    spoken_summary: the short spoken version already being said (≤50 words).
    Returns immediately; card delivery is async via WebSocket.
    """
    payload = {"type": "card", "card_type": type, "data": data, "spoken_summary": spoken_summary}
    log.info("display_data called: type=%s, callbacks=%d", type, len(_display_callbacks))

    if _display_callbacks:
        for loop, callback in _display_callbacks.values():
            asyncio.run_coroutine_threadsafe(callback(payload), loop)
    else:
        # No WebSocket yet (testing) — log to console
        import json
        print(f"[display_data] {type}: {json.dumps(data, default=str)[:120]} …")

    return {"delivered": True, "type": type}
