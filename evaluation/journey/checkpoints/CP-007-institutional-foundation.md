# CP-007 — accepted defects, institutional reality check and first check-ins

Recorded on: 2026-09-08. Period covered: current review/research/check-in increment.
Provenance: contemporaneous. Author: Codex (AI-assisted).
Predecessor: [CP-006](CP-006-continuity.md).
Sources: owner acceptance in the conversation; [decision 0005](../../decisions/0005-counselling-defects.md);
[sourced research](../../research/2026-09-08-institutional-counselling.md).

## Before
Counselling findings were proposed, and accumulated implementation/history remained
uncommitted. The suggested fix focused on course-tool constraints and prerequisites.

## Evidence and limitations
Owner accepted the defect categories and requested an institutional reality check.
Public Monash/RMIT/VTAC sources distinguish course guidance, applicant evidence,
formal assessment and selection-rank semantics. They do not verify a counsellor's
internal CRM permissions or workflow. No staff interview or system access occurred.
The existing 45 tests, including DB integration, passed before the initial commit.

## Changed thinking
The foundation needs explicit evidence and authority boundaries, not only stronger
filters. “Full-time” is workload, not proof of campus delivery. Prior lowest
selection rank is not necessarily a hard minimum. Missing prerequisites remain
unknown; entry routes can include alternative experience criteria. These are design
implications, not retrospective changes to Kingsford's synthetic truth.

## Dispositions
Owner accepts qualification/mode defects and incomplete material handover context;
authorizes foundations and Git check-ins. Proposed implementation is documented in
[the suitability contract](../../domains/education/suitability-foundation.md).
No blanket pass/fail is assigned to all eight cases; isolated clarification remains
unadjudicated. The first local commit, `913859f`, records the accumulated foundation
and CP-001–006. It is one retrospective baseline commit, not fabricated historical
commits for each milestone. No push or deployment.

## Next and revisit trigger
Implement a small explicit synthetic constraint/eligibility representation, shared
by tool payloads and cards, with regression cases; rerun the counselling journeys.
Validate real institution data ownership, field semantics, access and escalation
through an SME walkthrough before claiming partner readiness. Research-driven
extensions are proposed and should not inflate the demo into an admissions engine.
