# Waypoint (Clara) — Manual UI Test Suite

**Agent:** Clara — Kingsford University Course Counsellor  
**Environments:**
- Local dev: `http://localhost:8080/`
- Production: `http://<mac-mini-lan-ip>:8080/` (via SSH tunnel)

**Last updated:** 2026-06-01  
**Version:** 2.0 (post event-registration build)

---

## How to Run

1. Navigate to the agent URL in a browser
2. For each test case, click **End Session → New Session** to clear conversation context
3. Wait for Clara's greeting to complete (~3 seconds)
4. Enter the **Prompt** exactly as written and send (typed or spoken)
5. Evaluate against **Expected Behaviour** and **Pass Criteria**
6. Mark each test: ✅ Pass / ⚠️ Partial / ❌ Fail — note any gaps

---

## Automation Coverage Key

Tests marked with 🤖 have corresponding automated coverage in `eval_suite.py` and do not need to be re-run manually on every release. Tests marked 👤 are manual-only.

| Symbol | Meaning |
|--------|---------|
| 🤖 L1 | Covered by eval_suite Layer 1 (tool correctness, direct DB call) |
| 🤖 L2 | Covered by eval_suite Layer 2 (routing, Gemini text API) |
| 🤖 L2b | Covered by eval_suite Layer 2b (multi-turn routing) |
| 👤 | Manual only — no automated equivalent |

> **Run the automated suite first:** `python eval_suite.py`  
> If all automated tests pass, focus manual testing on 👤 items.

---

## Category 1 — Course Discovery & Information

*Automation: 🤖 L1 covers tool shape; 🤖 L2 covers routing (R00–R03). Manual tests verify card rendering, content quality, and edge case phrasing.*

| # | Test Name | Prompt | Expected Behaviour | Pass Criteria | Auto |
|---|-----------|--------|--------------------|---------------|------|
| 1.1 | Nursing course detail | `Can you tell me more about the Bachelor of Nursing?` | Full course detail card: duration, ATAR, fees, mode, entry requirements, career outcomes | Card renders without truncation; dedicated Entry Requirements field visible | 🤖 L1, L2 |
| 1.2 | Computer Science catalogue | `What computer science courses do you offer?` | Multiple CS-related course cards returned | ≥ 2 relevant courses; match % ≥ 70% | 🤖 L1, L2 |
| 1.3 | Engineering programmes | `Do you have any engineering programs I can apply for?` | Agent lists digital-focused engineering programs; proactively clarifies no civil/mechanical/electrical | No false promises of unavailable specialisations; scope clarification in spoken response | 👤 |
| 1.4 | Allied health options | `I'm interested in nursing or allied health — what degrees do you have?` | Nursing + allied health degree cards displayed | ≥ 2 allied health cards; ATAR cutoffs visible on cards | 🤖 L1 |
| 1.5 | ATAR cutoffs table | `What are the ATAR cutoffs for Kingsford courses?` | Knowledge card with full ATAR cutoffs table | Table renders completely; no truncation to `l...` or `...`; all rows visible | 👤 |
| 1.6 | Postgraduate entry requirements | `What are the entry requirements for the Master of Data Science?` | Course detail card with dedicated Entry Requirements field shown | Entry requirements not buried in About text; own labelled field at top of card | 🤖 L1 |
| 1.7 | Non-existent course (edge) | `Do you have a Bachelor of Law degree?` | Agent confirms Law is not offered; suggests relevant alternatives | No hallucinated course; graceful redirect to alternatives | 👤 |
| 1.8 | Off-topic query (edge) | `What's the best recipe for chocolate cake?` | Agent stays in scope; declines; offers university help | No off-topic content returned; polite boundary | 👤 |

---

## Category 2 — Personalised Course Recommendations

*Automation: 🤖 L1 covers `recommend_courses` shape; 🤖 L2 covers routing (R04–R06). Manual tests verify ATAR filtering display, match score quality, and conversational memory.*

| # | Test Name | Prompt | Expected Behaviour | Pass Criteria | Auto |
|---|-----------|--------|--------------------|---------------|------|
| 2.1 | STEM aptitude | `I love maths and problem solving and I'm strong in physics and logical thinking. What courses would suit me?` | STEM courses recommended with match scores | Match scores ≥ 70%; relevant STEM courses only; no Business Administration in results | 🤖 L2 |
| 2.2 | Online science preference | `I'm strong in science and prefer studying online. What would you recommend?` | Online science/health-adjacent courses returned; Online study mode flagged on cards | ≥ 2 online options (incl. Psychology Online, BBA Online); mode = "Online" clearly shown | 👤 |
| 2.3 | Arts & design aptitude | `I love art and design, and I'm strong at visual communication and drawing. Can you recommend courses for me?` | Creative Arts / Digital Media / Communications courses recommended | Relevant arts courses returned; no STEM mismatch | 🤖 L2 |
| 2.4 | ATAR-filtered recommendations | `My ATAR is 75. What courses can I get into at Kingsford?` | Only courses with ATAR cutoff ≤ 75 shown | No courses with cutoff > 75 in results; ATAR filter respected | 🤖 L1 |
| 2.5 | Context memory follow-up | `Tell me more about the Bachelor of Finance you mentioned` *(after a prior turn recommending Finance)* | Agent recalls prior recommendation and provides full course detail | Correct course detail shown; no hallucination of wrong course | 🤖 L2b |

---

## Category 3 — Admissions & University Knowledge

*Automation: 🤖 L2 routing covers R11–R16. Manual tests verify card content accuracy, markdown rendering, and conversational accuracy.*

| # | Test Name | Prompt | Expected Behaviour | Pass Criteria | Auto |
|---|-----------|--------|--------------------|---------------|------|
| 3.1 | Medicine (non-existent) | `What ATAR do I need to get into medicine?` | Agent proactively clarifies Medicine is NOT offered; explains feeder pathway to Melbourne/Monash; suggests Nursing/Public Health/Psychology | No ATAR given for Medicine; clear unavailability statement; pathway alternatives offered | 👤 |
| 3.2 | HECS-HELP | `How does HECS-HELP work for domestic students?` | Accurate explanation of deferred repayment scheme | Key facts correct (income threshold, deferred repayment, domestic only); info card returned | 🤖 L2 |
| 3.3 | Student visa | `What student visa do I need to study in Australia?` | Subclass 500 mentioned; official DHA guidance recommended | Visa subclass 500 named; agent recommends consulting official source | 🤖 L2 |
| 3.4 | Accommodation | `Is there on-campus accommodation available?` | Accurate response on Kingsford accommodation options | Correct for Kingsford's actual configuration; no hallucination | 🤖 L2 |
| 3.5 | Campus facilities | `What facilities does the campus have?` | Campus facilities listed (labs, library, sport, Innovation Lab, CyberLab) | Relevant facilities info card returned; no hallucination | 🤖 L2 |
| 3.6 | Business career prospects | `What are the career prospects for business graduates?` | Career outcomes card filtered to Business & Commerce faculty | Career card shows Business-relevant roles; not dominated by Engineering content | 👤 |
| 3.7 | Application deadlines | `How do I apply to Kingsford? What are the application deadlines?` | VTAC Deadlines calendar card shown; VTAC and direct postgrad pathways explained | VTAC deadlines card rendered; key 2027 dates visible | 👤 |
| 3.8 | RPL / Credit Transfer | `I already have a diploma in IT. Can I get credit towards a Bachelor of Computer Science?` | Dedicated RPL/Credit Transfer info card with process explanation | RPL card returned; 50% credit limit, 5-year currency, application process all visible | 👤 |

---

## Category 4 — Scholarships & Financial Support

*Automation: 🤖 L1 covers `search_scholarships` shape and type filters; 🤖 L2 covers routing (R17–R20).*

| # | Test Name | Prompt | Expected Behaviour | Pass Criteria | Auto |
|---|-----------|--------|--------------------|---------------|------|
| 4.1 | General scholarships | `Are there any scholarships I can apply for?` | Multiple scholarship cards with names, amounts, eligibility | ≥ 3 scholarships shown; eligibility criteria visible on each card | 🤖 L1, L2 |
| 4.2 | International financial help | `I'm an international student. Is there any financial help available?` | International-eligible scholarships shown; domestic-only options flagged as such | No domestic-only bursary shown without explicit "domestic students only" caveat; International Student Scholarship and Emergency Welfare Grant both surfaced | 👤 |
| 4.3 | Merit scholarships | `What merit scholarships does Kingsford offer for high achievers?` | Merit-based scholarship cards returned | Scholarship cards filtered to merit type; award amounts shown | 🤖 L1, L2 |
| 4.4 | Domestic hardship — no medical disclaimer | `My family is going through financial hardship. Is there any bursary support?` | Hardship fund cards returned; **no medical/health disclaimer** in response | Relevant financial support shown; NO text about seeing a healthcare professional | 👤 |
| 4.5 | International hardship | `I'm an international student and my family is facing financial hardship. Is there any emergency support for me?` | International Emergency Welfare Grant and interest-free loan surfaced; domestic-only options flagged | Agent explicitly distinguishes international-eligible from domestic-only options; emergency grant card shown | 👤 |
| 4.6 | Info session query (not scholarship) | `Are there any information sessions I can attend?` | Info session event cards returned — not scholarship cards | Event cards shown; no deflection to scholarships | 🤖 L2 |

---

## Category 5 — Event Discovery, Registration & Campus Tour Booking

*Automation: 🤖 L1 covers `book_campus_tour` and `search_events` tool shape; 🤖 L2 covers routing (R07–R10). The `register_for_event` tool has **no automated coverage yet** — all event registration tests are manual.*

| # | Test Name | Prompt / Action | Expected Behaviour | Pass Criteria | Auto |
|---|-----------|----------------|--------------------|---------------|------|
| 5.1 | Events this month | `What events are on this month?` | Events in current calendar month (June 2026) listed | ≥ 1 event in current month shown; if none, agent explains and shows upcoming | 🤖 L1 |
| 5.2 | Open Day discovery | `Is there an open day coming up soon?` | Open Day event card shown with date, description, and **Register with Clara** button | Event card appears; "Register with Clara" button present (not a dead external link) | 👤 |
| 5.3 | International info sessions | `Are there any information sessions for international students?` | International Students Welcome Session (or equivalent) returned | Relevant info session card shown; "Register with Clara" button present | 👤 |
| 5.4 | Campus tour — valid date | `I'd like to book a campus tour. My name is Alex Smith, email alex@example.com, for 2026-10-15, party of 2.` | Booking confirmed with `GT-XXXXX` reference; booking card shown | Booking card rendered with reference number; confirmation read aloud | 🤖 L1, L2 |
| 5.5 | Campus tour — past date | `I'd like to book a campus tour. My name is Alex Smith, email alex@example.com, for 2026-04-12, party of 2.` | Agent rejects past date with clear error; asks for a future date | Booking NOT created; explicit past-date rejection message; no `GT-XXXXX` issued | 🤖 L1 |
| 5.6 | Register with Clara — card button | Click **"Register with Clara"** on any future event card | Button sends `"I'd like to register for [event name]"` into the conversation; Clara responds asking for name and email | Chat message appears in transcript; Clara asks for name and/or email before attempting registration | 👤 |
| 5.7 | Event registration — happy path | `I'd like to register for the Open Day` → Clara asks for name/email → provide `Jordan Lee, jordan@example.com` | Clara collects name and email, calls `register_for_event`, returns `EV-XXXXX` confirmation card | `EV-XXXXX` format reference issued; Registration card shows event title, date, location, name, email | 👤 |
| 5.8 | Event registration — missing info | `I want to sign up for the Open Day` *(no name or email provided)* | Clara asks for full name; then asks for email; only calls tool once both are collected | Tool NOT called until both pieces of info are provided; no premature registration attempt | 👤 |
| 5.9 | Event registration — fully booked | Attempt to register (voice or button) for an event with 0 spots left | "Fully Booked" label shown on event card; if via voice, Clara states event is full and offers to find alternatives | No `EV-XXXXX` issued; "Fully Booked" visible on card; agent suggests alternative events | 👤 |

---

## Category 6 — Vision / Multimodal Scenarios

*Automation: None — all vision tests are manual. Requires real image upload via the camera icon.*

| # | Test Name | Method | Expected Behaviour | Pass Criteria | Auto |
|---|-----------|--------|--------------------|---------------|------|
| 6.1 | Academic transcript | Upload transcript image → `Based on my results, what courses would suit me?` | Clara reads subject grades and recommends matched courses | Relevant course recommendations based on visible subjects | 👤 |
| 6.2 | Merit certificate | Upload award certificate → `I have this achievement — are there scholarships I could apply for?` | Agent identifies achievement type; suggests merit scholarships | Scholarship cards returned; agent references certificate content | 👤 |
| 6.3 | Creative portfolio | Upload design/artwork → `I've created this — what creative courses would you recommend?` | Agent recognises creative content; recommends arts/design courses | Arts/design courses recommended; agent references the visual | 👤 |
| 6.4 | Environmental cue | Upload hospital/clinical environment image | Agent picks up on healthcare context; suggests health-related courses without explicit prompting | Health/Nursing/Allied Health courses surfaced | 👤 |
| 6.5 | Identity document | Upload passport image | Agent declines to process personal identity documents; recommends official channels | PII refusal triggered; agent does not extract or repeat passport data | 👤 |
| 6.6 | Campus exploration | Upload image of a campus building or sign | Agent treats as Kingsford campus context; offers campus-related info or tour booking | Campus info, tour booking, or events surfaced | 👤 |

---

## Category 7 — Regression & Edge Cases

*Run this category after any agent.py, tools.py, or frontend change.*

| # | Test Name | Prompt / Action | Expected Behaviour | Pass Criteria | Auto |
|---|-----------|----------------|--------------------|---------------|------|
| 7.1 | Course comparison card | `Can you compare the Bachelor of Computer Science and Bachelor of Software Engineering?` | Side-by-side Course Comparison card rendered | Comparison card type displayed in Research Panel; both courses shown with all fields | 👤 |
| 7.2 | Medical disclaimer scope | Run test 4.4 or 4.5 (financial hardship) | **No** medical/healthcare disclaimer appears in response | Medical disclaimer only in health/medical query contexts; never in financial support responses | 👤 |
| 7.3 | Match % quality | Run any recommendation query (e.g. 2.1) | Match percentages are meaningful and differentiated | Scores ≥ 70%; not uniformly low (old behaviour: 44–57%); range across results | 🤖 L1 |
| 7.4 | Card content not truncated | Run any query returning multiple info cards | All card content renders fully | No `...` truncation on any card field; info cards scroll if content is long | 👤 |
| 7.5 | Event registration card rendering | Complete an event registration (test 5.7) | `EV-XXXXX` Registration card renders correctly in Research Panel | Card shows: reference (EV-XXXXX format), event title, date, location, student name, email; "Registration" pill appears in nav bar | 👤 |

---

## Scoring Template

| Category | Total Tests | ✅ Pass | ⚠️ Partial | ❌ Fail | Score |
|----------|------------|--------|-----------|--------|-------|
| 1. Course Discovery | 8 | | | | /8 |
| 2. Recommendations | 5 | | | | /5 |
| 3. Admissions & Knowledge | 8 | | | | /8 |
| 4. Scholarships & Finance | 6 | | | | /6 |
| 5. Events, Registration & Tour | 9 | | | | /9 |
| 6. Vision / Multimodal | 6 | | | | /6 |
| 7. Regression & Edge Cases | 5 | | | | /5 |
| **TOTAL** | **47** | | | | **/47** |

---

## Severity Classification

When logging failures, tag each with a severity:

| Level | Label | Definition |
|-------|-------|-----------|
| P0 | Critical | Agent returns factually wrong information (e.g. offers Medicine degree, books non-existent course) or crashes |
| P1 | High | Core feature broken: ATAR filter allows ineligible courses, booking accepts past dates, registration tool not called, EV-XXXXX not issued |
| P2 | Medium | Feature works but with notable gaps: domestic bursary shown to international student without caveat, missing CTA button, medical disclaimer in wrong context |
| P3 | Low | Minor UX issues: card truncation, sentence formatting glitch, match % display issue |

---

## Relationship to Automated Eval Suite (`eval_suite.py`)

The automated suite (`python eval_suite.py`) and this manual test suite are **complementary, not redundant**:

| What | Where tested |
|------|-------------|
| Tools return correct response shapes (fields, types) | 🤖 `eval_suite.py` Layer 1 |
| Tools route correctly for all 8 use cases | 🤖 `eval_suite.py` Layer 2 |
| Multi-turn routing coherence (context retention) | 🤖 `eval_suite.py` Layer 2b |
| Voice pipeline, spoken response quality | 👤 Manual |
| Card UI renders correctly (no truncation, correct layout) | 👤 Manual |
| Event registration end-to-end (voice → EV-XXXXX card) | 👤 Manual |
| Medical disclaimer suppression | 👤 Manual |
| International hardship caveat accuracy | 👤 Manual |
| Vision / image upload flows | 👤 Manual |
