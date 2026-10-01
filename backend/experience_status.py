"""Evidence-backed professional IT experience resolution for course discovery.

Deliberately Limited Supported Grammar & Evidence Contract:
============================================================
This module implements a bounded deterministic evidence contract for professional
IT experience. It does NOT claim general natural-language understanding. Unsupported
or ambiguous wording remains unknown (effective: None) and requires student clarification.

1. Speaker Self-Attribution (First Person):
   - A disclosure or explicit zero declaration must be directly bound to the student
     via first-person self-attribution ('I', 'I have', "I've been", 'my experience').
   - Third-person subjects ('my sister', 'my brother', 'someone', 'he', 'she') and
     reported speech ('my sister said...', 'he told me...') are not self-attributed and
     are ignored (producing None).

2. Factual Assertion Framing (Non-Interrogative, Non-Hypothetical):
   - Questions and interrogatives (ending with '?' or opening with auxiliary inversion
     like 'Do I have to...', 'Is three years required?', 'Does this require...') are
     policy inquiries or uncertainty queries, not factual claims.
   - Hypotheticals and conditional scopes (governed by 'if', 'suppose', 'assuming',
     'what if', 'imagine', 'let's say', including 'for example, if...') do not assert
     actual history and produce None.

3. Explicit IT Domain & Duration Binding:
   - Duration and recognized IT domain (IT support, technical support, cybersecurity,
     cloud computing, software engineering, systems/network administration, devops,
     programming) must be bound within the student's assertion.
   - Unrelated employment (retail, hospitality, nursing, sales, construction, general
     customer service) does NOT establish IT experience.

4. Explicit Zero Experience:
   - Must be explicitly declared by the student in words ('I have no IT experience',
     'I don't have any IT experience', 'I've never worked in IT').
   - Third-person statements ('my sister has no IT experience') produce None.
   - Statements about qualifications or certifications ('I don't have IT qualifications',
     'I don't have IT certifications') do not establish zero work experience; they leave experience unknown (None).
   - Lack of mention, high school completion, or non-IT jobs leave experience unknown (None),
     never inferred as zero.

5. Clarification Instead of Duration Inference:
   - Positive evidence must explicitly name professional experience or working/worked
     in IT. Generic "years in IT" or "IT experience" remains unknown.
   - Partial refinements such as "only one year was professional" do not establish
     an exact duration. Relevant limitations clear the prior duration to unknown.
   - Unknown returns needs_clarification and a suggested question. Clara asks only
     when the answer materially affects suitability, and does not repeatedly ask.

6. Corrections & Retractions:
   - Contradictions of duration ('Actually, I do not have three years of IT experience')
     or IT attribution ('I worked in retail, not IT', 'that was my brother, not me')
     invalidate prior claims, resetting effective experience to None.
   - Statements unrelated to IT experience ('My brother wants Business, not me') leave
     previously established IT experience intact.

7. Three Effective States & Provenance Preservation:
   - Effective value is strictly: positive float (e.g. 3.0), explicit 0.0, or None (unknown).
   - Provenance records proposed value, effective value, source message, matched text, and
     one of: 'evidence', 'unsupported', 'unspecified', 'contradicted', 'retracted', 'missing_context'.
   - None is preserved throughout; never converted to zero downstream.
"""
from __future__ import annotations

import re
from typing import Optional


CLARIFICATION_QUESTION = (
    "How many years have you worked professionally in IT, excluding study and personal projects?"
)

# Word to number mapping
_WORD_TO_NUM = {
    "zero": 0.0,
    "no": 0.0,
    "half": 0.5,
    "one": 1.0,
    "two": 2.0,
    "three": 3.0,
    "four": 4.0,
    "five": 5.0,
    "six": 6.0,
    "seven": 7.0,
    "eight": 8.0,
    "nine": 9.0,
    "ten": 10.0,
}


def _parse_years(val_str: str) -> Optional[float]:
    val_clean = val_str.strip().lower()
    if val_clean in _WORD_TO_NUM:
        return _WORD_TO_NUM[val_clean]
    try:
        return float(val_clean)
    except ValueError:
        return None


_YEAR_VALS = r"\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten"

_IT_FIELD = (
    r"(?:IT(?:\s+support)?|tech(?:nology|nical)?(?:\s+support)?|"
    r"information\s+technology|software(?:\s+(?:development|engineering|developer|engineer))?|"
    r"web(?:\s+(?:development|developer))?|systems?(?:\s+admin(?:istrator|istration)?)?|"
    r"networks?(?:\s+admin(?:istrator|istration)?|\s+engineer(?:ing)?)?|cybersecurity|"
    r"cloud(?:\s+computing)?|devops|programming|programmer|helpdesk|tech)"
)

# Sentence-level question / interrogative detection
_IS_QUESTION = re.compile(
    r"\?|"
    r"^\s*(?:is|are|does|do|can|could|would|will|am\s+i|have\s+i)\b",
    re.IGNORECASE,
)

# Hypothetical / conditional framing (covers standalone 'if' and embedded 'for example, if')
_IS_HYPOTHETICAL = re.compile(
    r"\b(?:if|suppose|supposing|assuming|what\s+if|imagine|let'?s\s+(?:say|suppose|assume))\b",
    re.IGNORECASE,
)

# Reported speech / other-person attribution framing
_REPORTED_SPEECH = re.compile(
    r"\b(?:my\s+(?:sister|brother|mother|father|friend|colleague|boss|partner)|someone|he|she|they)\s+(?:said|told|claimed|thinks?|mentioned)\b|"
    r'["\']\s*i\s+(?:have|worked|hold)',
    re.IGNORECASE,
)

# Explicit zero IT experience patterns (strictly bound to student self-attribution and work/experience nouns)
_ZERO_SELF_PATTERNS = [
    re.compile(
        rf"\bi(?:(?:\'ve|\s+have)?\s+never\s+worked\s+in\s+{_IT_FIELD})\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\bi\s+(?:have\s+no|haven\'?t\s+got|have\s+not\s+got|don\'?t\s+have|do\s+not\s+have)\s+(?:actually\s+|currently\s+|really\s+)?(?:any\s+)?(?:professional\s+|work\s+)?{_IT_FIELD}\s+(?:experience|background|history|work)\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\bi\s+(?:have|hold|possess)\s+(?:zero|0|no)\s+years?(?:\s+of)?\s*(?:professional\s+|work\s+)?{_IT_FIELD}(?:\s+(?:experience|work))?\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\bno\s+{_IT_FIELD}\s+(?:experience|work)\s+(?:for\s+me|on\s+my\s+end)\b",
        re.IGNORECASE,
    ),
]

# Negation of a specific duration / prior claim by student
_NEGATION_SELF_PATTERNS = [
    re.compile(
        rf"\bi\s+(?:do\s+not|don'?t|haven'?t|have\s+not)\s+(?:have|got|hold)?\s*({_YEAR_VALS})\s+years?\s+(?:of\s+)?(?:professional\s+)?{_IT_FIELD}",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\bi\s+(?:do\s+not|don'?t)\s+have\s+that\s+(?:experience|background)\b",
        re.IGNORECASE,
    ),
]

# Scope-specific retraction of IT experience
_RETRACTION_SELF_PATTERNS = [
    # Non-IT field correction (work was in non-IT, not IT)
    re.compile(
        rf"\bi\s+(?:worked|worked\s+in|work\s+in|worked\s+as)\s+(?:in\s+)?(?:retail|hospitality|sales|accounting|[a-z]+),?\s*(?:not|rather\s+than)\s+(?:in\s+)?(?:it|tech)\b",
        re.IGNORECASE,
    ),
    # Mistake or misspeaking acknowledgment about work/experience
    re.compile(
        r"\b(?:scratch\s+that|misspoke|made\s+a\s+mistake)\b",
        re.IGNORECASE,
    ),
    # Identity attribution retraction regarding the claim
    re.compile(
        r"\b(?:sorry,?\s+)?that\s+was\s+(?:my\s+[a-z]+|someone\s+else),?\s*not\s+me\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:referring\s+to|that\s+was)\s+my\s+[a-z]+.*(?:work|job|experience|it)\b",
        re.IGNORECASE,
    ),
]

# Partial refinement pattern: invalidates a linked duration; never supplies a new one
_PROFESSIONAL_REFINE_PATTERN = re.compile(
    rf"\b(?:only\s+)?({_YEAR_VALS})\s+years?\s+(?:was|were|is)\s+professional\b",
    re.IGNORECASE,
)

# Pattern identifying non-professional qualifiers (academic, personal, study)
_QUALIFICATION_NEGATION_PATTERN = re.compile(
    r"^(?:(?:that|it|the|my)\s+(?:experience|work|background)\s+(?:was|is)|(?:that|it)\s+(?:was|is))\s+"
    r"(?:not\s+professional|non-professional|unpaid|just|only|all|mostly)?\s*"
    r".*\b(?:coursework|study|studying|academic|university|college|personal\s+projects?|hobby|hobbies|not\s+professional|non-professional|not\s+(?:paid\s+)?work|unpaid|not\s+employment)\b|"
    r"^(?:only|the\s+rest|not\s+all|none|some|all|mostly)\b.*\b(?:professional|coursework|study|studying|hobby|personal\s+projects?)\b",
    re.IGNORECASE,
)

# Qualifications that affirm employment or explicitly negate non-professional activity
def _is_affirmative_work_defense(c: str) -> bool:
    # Check if employment/paid work is negated:
    negated_work = bool(re.search(
        r"\b(?:not|never|no|without|unpaid|non-)\s*(?:paid\s+)?(?:work|employment|job)\b",
        c,
        re.IGNORECASE,
    ))
    if negated_work:
        return False
    # Check if work/employment is affirmed:
    has_work = bool(re.search(
        r"\b(?:employment|paid\s+work|job|actual\s+work|workplace)\b",
        c,
        re.IGNORECASE,
    ))
    # Check if study/coursework is negated:
    negated_study = bool(re.search(
        r"\b(?:not|rather\s+than|instead\s+of|never)\s+(?:just\s+)?(?:coursework|study|studying|academic|personal\s+projects?|hobby)\b",
        c,
        re.IGNORECASE,
    ))
    return has_work and negated_study

# Third party subjects whose statements within a turn must not bind anaphorically to student IT antecedent
_THIRD_PARTY_SUBJECT = re.compile(
    r"\b(?:my\s+(?:sister|brother|mother|father|friend|colleague|partner)|someone|he|she|they)\b",
    re.IGNORECASE,
)

# Explicit first-person self-attribution markers that override third-party turn context
_EXPLICIT_SELF_ATTR = re.compile(
    r"\b(?:my\s+(?:own\s+)?(?:experience|work|background)|mine)\b|^(?:i\b|i've\b|i'm\b)",
    re.IGNORECASE,
)

# Non-IT job roles that isolate refinement clauses from IT experience
_NON_IT_JOBS = re.compile(
    r"\b(?:retail|nursing|hospitality|sales|accounting|construction|teaching|doctor|lawyer|clerk)\b",
    re.IGNORECASE,
)

# Optional professional / full-time adverb or adjective modifier
_PROF_MODIFIERS = r"(?:professionally|full-time|full\s+time|as\s+a\s+professional|in\s+a\s+professional\s+role)"

# Positive IT experience patterns strictly bound to first-person self-attribution
_POSITIVE_SELF_PATTERNS = [
    # I have X years of experience in IT
    re.compile(
        rf"\bi(?:(?:\'ve|\s+have)\s+(?:got|had)?|\s+(?:have|got|hold|possess))\s+({_YEAR_VALS})\s+years?(?:\s+of)?\s+experience\s+(?:in|with)\s+{_IT_FIELD}(?:\s+{_PROF_MODIFIERS})?\b",
        re.IGNORECASE,
    ),
    # I've been working in IT for X years
    re.compile(
        rf"\bi(?:(?:\'ve|\s+have)\s+been\s+working|\s+worked|\'ve\s+worked)\s+(?:{_PROF_MODIFIERS}\s+)?(?:in|as(?:\s+an?|\s+the)?|with)\s+{_IT_FIELD}(?:\s+{_PROF_MODIFIERS})?\s+for\s+({_YEAR_VALS})\s+years?(?:\s+{_PROF_MODIFIERS})?\b",
        re.IGNORECASE,
    ),
    # I have X years of [professional/full-time] IT experience / support
    re.compile(
        rf"\bi(?:(?:\'ve|\s+have)\s+(?:got|had)?|\s+(?:have|got|hold|possess))\s+({_YEAR_VALS})\s+years?(?:\s+of)?\s+(?:(?:professional|full-time|full\s+time)\s+)?{_IT_FIELD}(?:\s+experience|\s+support)?(?:\s+{_PROF_MODIFIERS})?\b",
        re.IGNORECASE,
    ),
    # I have X years working in IT
    re.compile(
        rf"\bi(?:(?:\'ve|\s+have)\s+(?:got|had)?|\s+(?:have|got|hold|possess))\s+({_YEAR_VALS})\s+years?(?:\s+of)?\s+(?:working\s+in\s+){_IT_FIELD}(?:\s+{_PROF_MODIFIERS})?\b",
        re.IGNORECASE,
    ),
    # I have X years in IT
    re.compile(
        rf"\bi(?:(?:\'ve|\s+have)\s+(?:got|had)?|\s+(?:have|got|hold|possess))\s+({_YEAR_VALS})\s+years?\s+(?:in|\s+of)\s+{_IT_FIELD}(?:\s+{_PROF_MODIFIERS})?\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\bi(?:(?:\'ve|\s+have)\s+(?:got|had)?|\s+(?:have|got|hold|possess))\s+({_YEAR_VALS})\s+year\s+in\s+{_IT_FIELD}(?:\s+{_PROF_MODIFIERS})?\b",
        re.IGNORECASE,
    ),
    # I have only X year(s) in IT
    re.compile(
        rf"\bi(?:(?:\'ve|\s+have)\s+(?:got|had)?|\s+(?:have|got))\s+only\s+({_YEAR_VALS})\s+years?\s+(?:in|\s+of)\s+{_IT_FIELD}(?:\s+{_PROF_MODIFIERS})?\b",
        re.IGNORECASE,
    ),
    # I worked in IT for X years
    re.compile(
        rf"\bi\s+worked\s+(?:{_PROF_MODIFIERS}\s+)?in\s+{_IT_FIELD}(?:\s+{_PROF_MODIFIERS})?\s+for\s+({_YEAR_VALS})\s+years?(?:\s+{_PROF_MODIFIERS})?\b",
        re.IGNORECASE,
    ),
]


def classify_clause(
    clause: str,
    active_it_antecedent: bool = False,
) -> tuple[str, Optional[float], Optional[str]]:
    """Classify a student clause under the bounded evidence contract.

    Returns:
        (event_type, years, matched_text)
        where event_type is one of:
          'DISCLOSURE': explicit disclosure of student professional IT experience duration
          'EXPLICIT_ZERO': explicit disclosure of zero student IT experience (years=0.0)
          'NEGATION': explicit negation of duration / threshold by student (years=None)
          'RETRACTION': explicit retraction of IT experience claim by student (years=None)
          'IRRELEVANT': irrelevant, ambiguous, hypothetical, or unsupported (years=None)
    """
    c = clause.strip().rstrip(".,;!")
    c = re.sub(r"^(?:(?:actually|sorry|to clarify|correction)[, :]*\s*)+", "", c, flags=re.I)
    if not c:
        return 'IRRELEVANT', None, None

    # Credentials (qualifications, certifications) are distinct from work experience.
    # Negations of credentials must not be interpreted as zero work experience.
    if re.search(r"\b(?:qualifications?|certifications?)\b", c, re.IGNORECASE):
        if not re.search(r"\b(?:experience|work)\b", c, re.IGNORECASE):
            return 'IRRELEVANT', None, None

    # A partial professional-duration refinement requires clarification.
    m_prof = _PROFESSIONAL_REFINE_PATTERN.fullmatch(c)
    if m_prof:
        return ('NEGATION', None, c) if active_it_antecedent else ('IRRELEVANT', None, None)

    # A qualification of the immediately preceding IT claim must not leave
    # its total active if the professional portion cannot be established.
    if active_it_antecedent and _QUALIFICATION_NEGATION_PATTERN.match(c):
        if not _is_affirmative_work_defense(c):
            return 'NEGATION', None, c

    # 2. Explicit zero experience with first-person self-attribution
    for pat in _ZERO_SELF_PATTERNS:
        m = pat.match(c)
        if m:
            return 'EXPLICIT_ZERO', 0.0, m.group(0)

    # 3. Negation of duration or claim with first-person self-attribution
    for pat in _NEGATION_SELF_PATTERNS:
        m = pat.match(c)
        if m:
            return 'NEGATION', None, m.group(0)

    # 4. Scope-specific retraction of IT experience
    for pat in _RETRACTION_SELF_PATTERNS:
        m = pat.match(c)
        if m:
            return 'RETRACTION', None, m.group(0)

    # 5. Positive disclosure with explicit first-person self-attribution
    for pat in _POSITIVE_SELF_PATTERNS:
        m = pat.match(c)
        if m:
            remainder = c[m.end():].strip()
            # If the clause contains a trailing qualification (e.g. coursework, personal projects),
            # it cannot establish a verified professional duration.
            if not re.search(r"\b(?:professional|professionally|working|worked|work|full-time|full\s+time)\b", m.group(0), re.I):
                return 'NEGATION', None, c
            if re.search(r"\b(?:coursework|academic|university|studying|hobby|personal\s+projects?)\b", remainder, re.I):
                return 'NEGATION', None, c
            y = _parse_years(m.group(1))
            if y is not None:
                return 'DISCLOSURE', y, m.group(0)

    return 'IRRELEVANT', None, None


classify_experience_clause = classify_clause


def resolve_it_experience(
    messages: Optional[list[dict]],
    proposed: Optional[float] = None,
) -> dict:
    """Resolve effective professional IT experience against conversation evidence.

    Preserves both the model's proposed value and the tool's effective value.
    If no session messages are available, produces None.
    If session messages exist, effective status requires explicit message evidence.

    Returns dict with keys:
      effective: Optional[float] — guarded value to be used in calculations
      proposed: Optional[float] — value proposed by model in tool call
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
            "needs_clarification": True,
            "clarification_question": CLARIFICATION_QUESTION,
            "unresolved_evidence": None,
            "reason": (
                f"No session message context available; cannot verify IT experience from evidence. "
                f"Proposed professional_it_years={proposed} guarded to None."
            ),
        }

    current_years: Optional[float] = None
    current_evidence: Optional[dict] = None
    last_retraction: Optional[dict] = None
    had_prior_evidence: bool = False

    for msg_idx, msg in enumerate(messages):
        text = msg.get("text", "") if isinstance(msg, dict) else str(msg)
        if not isinstance(text, str) or not text.strip():
            continue

        # Split utterance into sentences preserving sentence boundary punctuation
        normalized = text.replace("’", "'").replace("‘", "'")
        turn_subject = "student" if current_years is not None else None
        sentence_chunks = re.finditer(
            r".+?(?:[!?\n]+|(?<!\d)\.+|\.(?!\d)|$)", normalized, re.DOTALL
        )
        for chunk in sentence_chunks:
            s = chunk.group(0).strip()
            if not s:
                continue

            # Update turn subject from sentence-level context if explicit
            s_has_third = bool(_THIRD_PARTY_SUBJECT.search(s))
            s_has_self = bool(_EXPLICIT_SELF_ATTR.search(s))
            if s_has_third and not s_has_self:
                turn_subject = "third_party"
            elif s_has_self:
                turn_subject = "student"

            # A limitation can invalidate the immediate claim or an existing
            # personal value. It never establishes a replacement duration.
            antecedent = None
            recent_non_it = False

            # Split clauses while tracking delimiters to preserve governing context across dependent clauses
            tokens = re.split(
                r"(;|"
                r"\b(?:but|however|although|whereas|except)\b|"
                r",?\s*\band\s+(?=i\b)|"
                r",\s*(?=\bi\s+)|"
                r",\s*(?=(?:only|all|most(?:ly)?|none|part|some|the\s+rest)\b))",
                s,
                flags=re.IGNORECASE,
            )

            pairs = []
            current_delim = ""
            for t in tokens:
                if not t:
                    continue
                if re.match(r"^(?:;|\b(?:but|however|although|whereas|except)\b|,?\s*\band\b|,)$", t.strip(), re.I):
                    current_delim = t.strip()
                else:
                    pairs.append((current_delim, t))
                    current_delim = ""

            governing_hypo = False
            governing_reported = False

            for delim, clause in pairs:
                c = clause.strip().rstrip(".,;!")
                c = re.sub(r"^(?:(?:actually|sorry|to clarify|correction)[, :]*\s*)+", "", c, flags=re.I)
                if not c:
                    continue

                c_has_self = bool(_EXPLICIT_SELF_ATTR.search(c))
                is_contrastive = bool(re.match(r"^(?:;|\b(?:but|however|although|whereas|except)\b)", delim, re.I))

                # Contrastive boundaries with explicit self-attribution break out of governing context
                if is_contrastive and c_has_self:
                    governing_hypo = False
                    governing_reported = False

                # 1. Clause-level question / interrogative check
                if (
                    clause.strip().endswith("?")
                    or _IS_QUESTION.search(c)
                    or re.match(r"^(?:is|are|can|could|would|do|does|did|will|should)\b", c, re.IGNORECASE)
                ):
                    continue

                # 2. Update and check governing hypothetical context across dependent clauses
                if _IS_HYPOTHETICAL.search(c):
                    governing_hypo = True
                if governing_hypo or _IS_HYPOTHETICAL.search(c):
                    continue

                # 3. Update and check governing reported-speech context across dependent clauses
                if _REPORTED_SPEECH.search(c):
                    governing_reported = True
                if governing_reported or _REPORTED_SPEECH.search(c):
                    continue

                # 4. Determine clause-level attribution:
                # Explicit self-attribution in the clause always targets the student.
                # Explicit third-party attribution targets the third party.
                # Anaphoric / demonstrative clauses inherit the turn's active subject.
                c_has_self = bool(_EXPLICIT_SELF_ATTR.search(c))
                c_has_third = bool(_THIRD_PARTY_SUBJECT.search(c))
                c_has_non_it = bool(_NON_IT_JOBS.search(c))

                if c_has_self and not c_has_third:
                    clause_subject = "student"
                    turn_subject = "student"
                    recent_non_it = False
                elif c_has_third and not c_has_self:
                    clause_subject = "third_party"
                    turn_subject = "third_party"
                else:
                    clause_subject = turn_subject

                # Apply employment-domain exclusions to the relevant person and clause:
                # Explicit student self-attribution is never vetoed by non-IT jobs in other clauses.
                if clause_subject == "student":
                    if c_has_self:
                        is_student_antecedent = not c_has_non_it
                    else:
                        is_student_antecedent = not (recent_non_it or c_has_non_it)
                else:
                    is_student_antecedent = False

                if c_has_non_it and clause_subject == "student":
                    recent_non_it = True

                evt, years, match = classify_clause(
                    c,
                    active_it_antecedent=(antecedent is not None or (
                        current_years is not None and is_student_antecedent
                    )),
                )

                antecedent = None
                if evt == 'DISCLOSURE':
                    current_years = years
                    current_evidence = {
                        "message_id": msg.get("id") if isinstance(msg, dict) else msg_idx + 1,
                        "text": text,
                        "match": match,
                        "years": years,
                    }
                    last_retraction = None
                    had_prior_evidence = True
                    antecedent = dict(current_evidence)
                elif evt == 'EXPLICIT_ZERO':
                    current_years = 0.0
                    current_evidence = {
                        "message_id": msg.get("id") if isinstance(msg, dict) else msg_idx + 1,
                        "text": text,
                        "match": match,
                        "years": 0.0,
                    }
                    last_retraction = None
                    had_prior_evidence = True
                    antecedent = None
                elif evt in ('NEGATION', 'RETRACTION'):
                    current_years = None
                    current_evidence = None
                    antecedent = None
                    last_retraction = {
                        "message_id": msg.get("id") if isinstance(msg, dict) else msg_idx + 1,
                        "text": text,
                        "match": match,
                    }
                # Unrelated clauses retain the value, but never the refinement link.

    effective = current_years
    prop_float = float(proposed) if proposed is not None else None

    if effective is None:
        if last_retraction is not None and had_prior_evidence:
            source = "retracted"
            reason = (
                f"Student message {last_retraction['message_id']} retracted or negated prior IT experience claims "
                f"('{last_retraction['match']}'). Guarded to None."
            )
        elif prop_float is not None:
            source = "unsupported"
            reason = (
                f"Model proposed professional_it_years={proposed}, but student messages contain "
                "no supported explicit professional IT work duration. Guarded to None."
            )
        else:
            source = "unspecified"
            reason = "No supported professional IT work duration established; retain unknown and clarify if relevant."
    else:
        assert current_evidence is not None
        if prop_float is None:
            source = "evidence"
            reason = (
                f"Student message {current_evidence['message_id']} established professional_it_years={effective} "
                f"('{current_evidence['match']}'); model proposed None."
            )
        elif prop_float == effective:
            source = "evidence"
            reason = (
                f"Student message {current_evidence['message_id']} confirmed professional_it_years={effective} "
                f"('{current_evidence['match']}')."
            )
        else:
            source = "contradicted"
            reason = (
                f"Model proposed professional_it_years={proposed}, but student message {current_evidence['message_id']} "
                f"established {effective} ('{current_evidence['match']}'). Guarded to {effective}."
            )

    return {
        "effective": effective,
        "proposed": proposed,
        "evidence": current_evidence,
        "source": source,
        "reason": reason,
        "needs_clarification": effective is None,
        "clarification_question": CLARIFICATION_QUESTION if effective is None else None,
        "unresolved_evidence": last_retraction if effective is None else None,
    }
