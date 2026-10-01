"""Evidence-backed degree status resolution for course discovery.

Enforces strict boundary between student-disclosed facts and unsupported inferences:
1. Degree status must be backed by explicit evidence from a specific student message.
2. Degree status remains None when evidence is missing, aspirational, hypothetical, or ambiguous.
3. Preserves both the model's proposed value and the tool's effective value.
4. Uses a chronological, state-machine update model over conversation turns and clauses.
5. Handles explicit declarations, retractions, identity corrections, and compound replacements.
6. Produces None when conversation context is unavailable, never silently trusting proposed values.
"""
from __future__ import annotations

import re
from typing import Optional


# Clause splitting on punctuation and contrastive/coordinating boundaries
_SPLIT_REGEX = re.compile(
    r"[.;!?\n]|(?:\b(?:but|however|although|though|whereas|except|and\s+then)\b)",
    re.IGNORECASE,
)

# Third-person reported speech attribution: statements attributed to others are NOT student disclosures
_THIRD_PERSON_ATTRIBUTION = re.compile(
    r"\b(?:my\s+(?:sister|brother|mother|father|friend|colleague|cousin|partner|wife|husband|coworker|manager|boss)|"
    r"someone|somebody|anyone|anybody|he|she|they)\s+(?:said|says|told\s+me|stated|wrote|mentioned|claims?)\b",
    re.IGNORECASE,
)

# Hypothetical / conditional frames: clauses framed hypothetically do NOT disclose facts
_HYPOTHETICAL_FRAME = re.compile(
    r"\b(?:let'?s\s+(?:suppose|say|assume)|suppose|supposing|assuming|assume|what\s+if|even\s+if|in\s+case|provided\s+that|"
    r"hypothetically|just\s+say|say\s+i\s+have|for\s+the\s+sake\s+of\s+argument|imagine\s+i)\b|"
    r"^\s*(?:if|whether)\b|"
    r"\b(?:would\s+that\s+help|could\s+that\s+help|would\s+it\s+matter|does\s+that\s+count)\b",
    re.IGNORECASE,
)

# In-progress / incomplete study: completion is not established
_INCOMPLETE_STUDY = re.compile(
    r"\b(?:in\s+progress|incomplete|unfinished|partially\s+completed|halfway|not\s+yet\s+(?:finished|completed|graduated)|"
    r"currently\s+enrolled|currently\s+studying(?:\s+towards)?|working\s+towards|pending\s+completion)\b",
    re.IGNORECASE,
)

# General / 3rd-party inquiries that ask about institutional rules/policy rather than stating personal status
_POLICY_INQUIRY = re.compile(
    r"\b(?:can|could|does|do|is\s+it\s+possible\s+for)\s+(?:someone|anyone|a\s+student|a\s+person|people|one|an\s+applicant)\b|"
    r"\bcan\s+(?:i|we|one|someone)\s+(?:apply|enrol|study|get\s+in)\s+without\b",
    re.IGNORECASE,
)

# Aspirational degree patterns: verbs targeting the acquisition of a degree (not existing possession)
_ASPIRATIONAL_DEGREE = re.compile(
    r"\b(?:want|wants|wanting|hope|hopes|hoping|look|looks|looking|need|needs|needing|"
    r"plan|plans|planning|wish|wishes|aim|aims|aiming|try|tries|trying|pursue|pursuing|"
    r"work\s+towards|working\s+towards|enrol\s+in|enrolling\s+in|apply\s+for|applying\s+for|"
    r"interested\s+in)\s+(?:to\s+)?(?:get|obtain|earn|complete|finish|do|have|study(?:\s+towards)?)?\s*"
    r"(?:a|an)?\s*(?:bachelor(?:'?s)?|undergraduate|university|tertiary|college)?\s*degree\b|"
    r"\b(?:want|hope|look|looking|need|plan|wish|aim|try|pursue|study)\s+(?:to\s+study|for)?\s*(?:a\s+)?bachelor(?:'?s)?\b",
    re.IGNORECASE,
)

# Negative declarations: strictly first-person assertions of NOT holding a degree
_FIRST_PERSON_NEG_PATTERNS = [
    re.compile(r"\bi\s+(?:don'?t|do\s+not)\s+(?:actually\s+|currently\s+|really\s+)?have\s+(?:a|an|any)?\s*(?:bachelor(?:'?s)?|undergraduate|university|tertiary|college)?\s*degree\b", re.IGNORECASE),
    re.compile(r"\bi\s+(?:haven'?t|have\s+not)\s+(?:actually\s+)?(?:got|completed|finished|done|obtained|earned)\s+(?:a|an|any)?\s*(?:bachelor(?:'?s)?|undergraduate|university|tertiary|college)?\s*degree\b", re.IGNORECASE),
    re.compile(r"\bi\s+(?:currently\s+|actually\s+)?have\s+no\s+(?:bachelor(?:'?s)?|undergraduate|university|tertiary|college)?\s*degree\b", re.IGNORECASE),
    re.compile(r"\bi\s+(?:am\s+)?without\s+(?:a|an|any)?\s*(?:bachelor(?:'?s)?|undergraduate|university|tertiary|college)?\s*degree\b", re.IGNORECASE),
    re.compile(r"\bi\s+(?:don'?t|do\s+not)\s+(?:actually\s+)?hold\s+(?:a|an|any)?\s*(?:bachelor(?:'?s)?|undergraduate|university|tertiary|college)?\s*degree\b", re.IGNORECASE),
    re.compile(r"\bi\s+never\s+(?:completed|finished|got|obtained|earned)\s+(?:a|an|any)?\s*(?:bachelor(?:'?s)?|undergraduate|university|tertiary|college)?\s*degree\b", re.IGNORECASE),
    re.compile(r"\bi\s+never\s+(?:went\s+to|attended|graduated\s+from)\s+university\b", re.IGNORECASE),
    re.compile(r"\bi\s+lack\s+(?:a|an)?\s*(?:bachelor(?:'?s)?|undergraduate|university|tertiary|college)?\s*degree\b", re.IGNORECASE),
    re.compile(r"\bfor\s+me,?\s*(?:i\s+have\s+)?no\s+(?:bachelor(?:'?s)?\s+)?degree\b", re.IGNORECASE),
    re.compile(r"\bno\s+bachelor(?:'?s)?\s+degree\s+for\s+me\b", re.IGNORECASE),
]

# Positive declarations: strictly first-person assertions of holding or having completed a degree
# Note: "degree" is MANDATORY after undergraduate/university/tertiary/college so "university diploma" NEVER matches!
_FIRST_PERSON_POS_PATTERNS = [
    re.compile(r"\bi\s+(?:actually\s+|already\s+|currently\s+|definitely\s+|really\s+)?(?:do\s+)?(?:have|hold|possess)\s+(?:a|an)?\s*bachelor(?:'?s)?(?:\s+degree)?\b", re.IGNORECASE),
    re.compile(r"\bi'?ve\s+(?:actually\s+|already\s+)?got\s+(?:a|an)?\s*bachelor(?:'?s)?(?:\s+degree)?\b", re.IGNORECASE),
    re.compile(r"\bi\s+(?:actually\s+|already\s+|currently\s+|definitely\s+|really\s+)?(?:do\s+)?(?:have|hold|possess)\s+(?:a|an)?\s*(?:undergraduate|university|tertiary|college)\s+degree\b", re.IGNORECASE),
    re.compile(r"\bi'?ve\s+(?:actually\s+|already\s+)?got\s+(?:a|an)?\s*(?:undergraduate|university|tertiary|college)\s+degree\b", re.IGNORECASE),
    re.compile(r"\bi\s+(?:actually\s+|already\s+|currently\s+|definitely\s+|really\s+)?(?:do\s+)?(?:have|hold|possess)\s+(?:a|an)?\s*degree\s+in\s+[a-z0-9\s/&-]+\b", re.IGNORECASE),
    re.compile(r"\bi\s+(?:actually\s+|already\s+)?(?:completed|finished)\s+(?:my|a|an)?\s*bachelor(?:'?s)?(?:\s+degree)?\b", re.IGNORECASE),
    re.compile(r"\bi'?ve\s+(?:actually\s+|already\s+)?(?:completed|finished)\s+(?:my|a|an)?\s*bachelor(?:'?s)?(?:\s+degree)?\b", re.IGNORECASE),
    re.compile(r"\bi\s+(?:actually\s+|already\s+)?(?:completed|finished)\s+(?:my|a|an)?\s*(?:undergraduate|university|tertiary|college)\s+degree\b", re.IGNORECASE),
    re.compile(r"\bi'?ve\s+(?:actually\s+|already\s+)?(?:completed|finished)\s+(?:my|a|an)?\s*(?:undergraduate|university|tertiary|college)\s+degree\b", re.IGNORECASE),
    re.compile(r"\bi\s+(?:actually\s+|already\s+)?graduated\s+with\s+(?:a|my)?\s*bachelor(?:'?s)?(?:\s+degree)?\b", re.IGNORECASE),
    re.compile(r"\bi\s+(?:actually\s+|already\s+)?graduated\s+from\s+university\s+with\s+(?:a|my)?\s*(?:bachelor(?:'?s)?\s+)?degree\b", re.IGNORECASE),
]

# Retraction / identity correction patterns: phrases where a student retracts, corrects attribution,
# or declares uncertainty about THEIR OWN prior degree statement.
# Must NOT match general course accreditation questions (e.g. "Is the Kingsford degree accredited?").
_RETRACTION_PATTERNS = [
    re.compile(r"\b(?:that\s+was|wasn'?t|referring\s+to|talking\s+about)\s+(?:my\s+[a-z]+|someone\s+else|not\s+me|somebody\s+else)\b", re.IGNORECASE),
    re.compile(r"\b(?:not\s+me|not\s+myself)\b", re.IGNORECASE),
    re.compile(r"\b(?:retract|disregard|ignore|forget|scratch|cancel|withhold)\b.*\b(?:my\s+earlier|earlier|previous|said|comment)\b", re.IGNORECASE),
    re.compile(r"\b(?:misspoke|made\s+a\s+mistake|mistake|misunderstood)\b.*\b(?:about|degree|qualification)\b", re.IGNORECASE),
    re.compile(r"\b(?:not\s+sure|unsure|uncertain|can'?t\s+confirm|not\s+confirmed|unconfirmed|might\s+not\s+be|may\s+not\s+be)\b.*\b(?:my\s+(?:degree|bachelor|qualification|study)|my\s+own\s+qualification)\b", re.IGNORECASE),
    re.compile(r"\bmy\s+(?:degree|qualification|bachelor)\b.*\b(?:might\s+not|may\s+not|is\s+not\s+sure|not\s+sure|unconfirmed)\b", re.IGNORECASE),
    re.compile(r"\bactually\s+(?:scratch\s+that|disregard|ignore)\s+about\s+(?:the|my|a)?\s*(?:bachelor|degree)\b", re.IGNORECASE),
    re.compile(r"\b(?:scratch\s+that|ignore\s+that|disregard\s+that)\b", re.IGNORECASE),
]


def classify_clause(clause: str) -> tuple[str, Optional[bool], Optional[str]]:
    """Classify a single student clause.

    Returns:
        (category, status, matched_text)
        where category is one of:
          'POS': explicit declaration that student holds a bachelor's degree (status=True)
          'NEG': explicit declaration that student does NOT hold a degree (status=False)
          'RETRACT': retraction or personal uncertainty about prior claim (status=None)
          'NONE': irrelevant, hypothetical, in-progress, reported speech, or ambiguous (status=None)
    """
    c = clause.strip()
    if not c:
        return 'NONE', None, None

    # 1. Skip third-person reported speech ("My sister said, 'I have a bachelor's degree.'")
    if _THIRD_PERSON_ATTRIBUTION.search(c):
        return 'NONE', None, None

    # 2. Skip hypothetical / conditional frames ("Let's suppose I have a bachelor's degree...")
    if _HYPOTHETICAL_FRAME.search(c):
        return 'NONE', None, None

    # 3. Skip in-progress or incomplete study ("I have a degree in progress")
    if _INCOMPLETE_STUDY.search(c):
        return 'NONE', None, None

    # 4. Skip general policy questions without a personal subject
    if _POLICY_INQUIRY.search(c) and not re.search(r"\bi\s+", c, re.IGNORECASE):
        return 'NONE', None, None

    # 5. Check negative declarations first (e.g. "I don't have a bachelor's degree")
    for pat in _FIRST_PERSON_NEG_PATTERNS:
        m = pat.search(c)
        if m:
            return 'NEG', False, m.group(0)

    # 6. Check positive declarations
    # Skip if the degree reference is purely aspirational
    if not _ASPIRATIONAL_DEGREE.search(c):
        for pat in _FIRST_PERSON_POS_PATTERNS:
            m = pat.search(c)
            if m:
                matched_str = m.group(0)
                # Safeguard: Ensure the clause does not state "diploma" or "certificate"
                # (e.g. "I have a university diploma" must not match)
                after_match = c[m.end():].strip().lower()
                if after_match.startswith("diploma") or after_match.startswith("certificate"):
                    continue
                # Also ensure incomplete study markers don't follow immediately (e.g. "in progress")
                if _INCOMPLETE_STUDY.search(after_match):
                    continue
                return 'POS', True, matched_str

    # 7. Check for retractions / identity corrections / personal qualification doubts
    for pat in _RETRACTION_PATTERNS:
        m = pat.search(c)
        if m:
            return 'RETRACT', None, m.group(0)

    return 'NONE', None, None


def extract_degree_evidence(text: str) -> tuple[Optional[bool], Optional[str]]:
    """Extract explicit declaration of bachelor degree status from student text.

    Returns:
        (True, matched_text) if explicit personal possession is declared.
        (False, matched_text) if explicit personal absence is declared.
        (None, None) if degree status is unmentioned, aspirational, hypothetical, or ambiguous.
    """
    if not isinstance(text, str) or not text.strip():
        return None, None

    # Quick check for third-person speech enclosing the whole message
    if _THIRD_PERSON_ATTRIBUTION.search(text) and not re.search(r"\bbut\s+i\b", text, re.IGNORECASE):
        return None, None

    clauses = _SPLIT_REGEX.split(text)

    # Inspect clauses chronologically so later clauses in the same message update state
    latest_status: Optional[bool] = None
    latest_match: Optional[str] = None

    for clause in clauses:
        cat, status, match = classify_clause(clause)
        if cat in ('POS', 'NEG'):
            latest_status = status
            latest_match = match
        elif cat == 'RETRACT':
            latest_status = None
            latest_match = None

    return latest_status, latest_match


def check_degree_retraction(text: str) -> Optional[str]:
    """Check if the text contains a retraction or doubt regarding prior personal degree claims."""
    if not isinstance(text, str) or not text.strip():
        return None
    clauses = _SPLIT_REGEX.split(text)
    for clause in clauses:
        cat, _, match = classify_clause(clause)
        if cat == 'RETRACT':
            return match
    return None


def resolve_degree_status(
    messages: Optional[list[dict]],
    proposed: Optional[bool] = None,
) -> dict:
    """Resolve effective degree status against conversation evidence.

    Preserves both the model's proposed value and the tool's effective value.
    If no session messages are available, produces None (never silently trusts proposed).
    If session messages exist, effective status requires explicit message evidence.

    Returns dict with keys:
      effective: Optional[bool] — guarded value to be used in calculations
      proposed: Optional[bool] — value proposed by model in tool call
      evidence: Optional[dict] — specific message and quote establishing status
      source: str — 'evidence' | 'unsupported' | 'unspecified' | 'contradicted' | 'retracted' | 'missing_context'
      reason: str — human-readable audit justification
    """
    if messages is None:
        return {
            "effective": None,
            "proposed": proposed,
            "evidence": None,
            "source": "missing_context",
            "reason": (
                f"No session message context available; cannot verify degree status from evidence. "
                f"Proposed has_bachelor_degree={proposed} guarded to None."
            ),
        }

    # Sequential state machine across chronological messages and clauses
    current_state: Optional[bool] = None
    current_evidence: Optional[dict] = None
    last_retraction: Optional[dict] = None

    for msg in messages:
        text = msg.get("text", "")
        if not isinstance(text, str) or not text.strip():
            continue

        # Check whole-message third person speech attribution
        if _THIRD_PERSON_ATTRIBUTION.search(text) and not re.search(r"\bbut\s+i\b", text, re.IGNORECASE):
            continue

        clauses = _SPLIT_REGEX.split(text)
        for clause in clauses:
            cat, status, match = classify_clause(clause)
            if cat in ('POS', 'NEG'):
                current_state = status
                current_evidence = {
                    "message_id": msg.get("id"),
                    "text": text,
                    "match": match,
                    "status": status,
                }
                last_retraction = None
            elif cat == 'RETRACT':
                current_state = None
                current_evidence = None
                last_retraction = {
                    "message_id": msg.get("id"),
                    "text": text,
                    "match": match,
                }

    effective = current_state

    if effective is None:
        if last_retraction is not None:
            source = "retracted"
            reason = (
                f"Student message {last_retraction['message_id']} retracted or called into doubt prior degree claims "
                f"('{last_retraction['match']}'). Guarded to None."
            )
        elif proposed is not None:
            source = "unsupported"
            reason = (
                f"Model proposed has_bachelor_degree={proposed}, but student messages contain "
                "no explicit evidence establishing degree status. Guarded to None."
            )
        else:
            source = "unspecified"
            reason = "Degree status unmentioned in student messages; model proposed None."
    else:
        assert current_evidence is not None
        if proposed is None:
            source = "evidence"
            reason = (
                f"Student message {current_evidence['message_id']} established has_bachelor_degree={effective} "
                f"('{current_evidence['match']}'); model proposed None."
            )
        elif proposed == effective:
            source = "evidence"
            reason = (
                f"Student message {current_evidence['message_id']} confirmed has_bachelor_degree={effective} "
                f"('{current_evidence['match']}')."
            )
        else:
            source = "contradicted"
            reason = (
                f"Model proposed has_bachelor_degree={proposed}, but student message {current_evidence['message_id']} "
                f"established {effective} ('{current_evidence['match']}'). Guarded to {effective}."
            )

    return {
        "effective": effective,
        "proposed": proposed,
        "evidence": current_evidence,
        "source": source,
        "reason": reason,
    }
