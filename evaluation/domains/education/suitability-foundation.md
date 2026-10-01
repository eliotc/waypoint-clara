# Course suitability foundation — proposed implementation contract

Date: 2026-09-08. Defects accepted by Eliot; the detailed fields and implementation
below are design proposals derived from the accepted behavior rules and
[institutional reality check](../../research/2026-09-08-institutional-counselling.md).
This document is a foundation for the fix, not a claim that runtime behavior is fixed.

## Minimum data we need to represent

| Object | Fields | Purpose |
|---|---|---|
| Course offering | Stable course/offer ID, qualification level, discipline, delivery mode, study load, campus, compulsory attendance/placement, intake, applicant cohort | Separate the course from the particular delivery option; full-time is not a synonym for on-campus |
| Entry rule | Rule ID, applicable offering/cohort/intake, prior qualification level/field, subject/grade conditions, relevant experience route, required evidence, source and assessment authority | Evaluate explicitly recorded routes; preserve AND/OR alternatives rather than inferring from a course name |
| Score evidence | Metric kind, value, period, adjustments policy, whether a hard minimum, guaranteed threshold or historical selection statistic | Avoid treating all ATAR-like numbers as hard filters |
| Student context | Goal, target study level, delivery/attendance constraints, study-load preference, prior qualifications, relevant experience, scores with metric/year | Ask only for missing information that can change the next decision |
| Fact provenance | Self-reported / institution-verified / inferred, source reference, recorded time, latest correction and superseded value | Preserve corrections without turning a model inference into a verified qualification |
| Source coverage | Snapshot/version, effective dates, which offerings were searched, authoritative completeness or unknown coverage | An empty top-k vector result cannot prove institution-wide absence |
| Advice result | Per-constraint met/unmet/unknown, supporting rule/fact IDs, suitable candidates, explicit alternatives, questions and escalation reasons | Make limitations visible to both Clara and the cards |
| Handover summary | Goal, constraints, qualifications, corrections, findings and evidence, unresolved questions, destination, actual action status | Preserve the context that matters to the next adviser; summary prepared is not handover completed |

Fields beyond our current source data stay explicitly unavailable. This is not an
instruction to collect sensitive documents or implement a full admissions engine.
Use student self-report for the demo, label it, and preserve unresolved eligibility.

## Minimum assessment semantics

For each relevant requirement: `met`, `unmet`, or `unknown`, with evidence.
“Met” means compatible with the facts and rule evaluated, not admitted. Known unmet
hard constraints prevent placement in suitable matches. Unknown mandatory facts
prevent unqualified suitability claims and identify a question or referral.
Alternatives explicitly name the constraint the student would have to change.
An OR entry rule remains potentially satisfiable if another route is unknown;
it is not rejected merely because one route fails. Semantic relevance ranks
candidates after explicit constraints; similarity scores are not admission odds.

Do not encode missing entry requirements as “none required.” Do not infer attendance
from load. Source conflicts, stale rules and missing coverage yield uncertainty.
Every claimed check must have a source; a generic confidence percentage cannot
substitute for evidence. Definitive institutional decisions remain out of scope.

## Apply this incrementally to our synthetic data

1. Preserve the existing run and dataset-v2 convention. Its `atar_cutoff` was used
   as a synthetic filter; its meaning is not transferable to a real selection rank.
2. Create an explicit versioned mapping for the small set of relevant synthetic
   course requirements. Keep unmapped/missing requirements unknown; do not build a
   universal regex eligibility parser over prose or fabricate authoritative facts.
3. Give both course-search tools the relevant student context and return compact
   level, mode, prerequisite and per-constraint evidence, not names alone. Ensure
   the card uses the same assessment. Ask a relevant follow-up when an unknown
   fact affects the answer; do not ask repeatedly for disclosed information.
4. Preserve material unresolved issues in the human-contact summary. No actual
   transfer/booking integration is implied by this change.
5. Add deterministic cases below, then rerun EXP-LIVE-002's unchanged scenarios.
   If data meaning changes, use a new dataset descriptor and explicitly label
   the comparison as a system/data change, not a model-only improvement.

## Required checks for the implementation

- School leaver without degree/experience: a degree-or-experience route is unmet;
  it cannot appear as an unqualified suitable postgraduate recommendation.
- Experienced applicant: honor an explicit alternative entry route; no blanket
  postgraduate exclusion. Insufficient facts or assessment-required route stays unknown.
- Online-only: known campus attendance conflicts; online label with unknown placement
  requirements does not establish fully remote attendance compatibility.
- Historical selection rank above reported ATAR: no hard exclusion based on that
  statistic alone. Separate explicitly defined synthetic/hard minimum semantics.
- Missing prerequisites: unknown, not automatic eligibility or categorical rejection.
- Corrected constraint: subsequent tool assessment and card use latest facts.
- No matching offering: state the coverage of the search and qualify alternatives.
- Handover: preserve qualifications, constraints and unresolved eligibility; no claim
  of submission/transfer without action evidence.

The institutional integration questions remain research work. The next code change
should implement the smallest explicit synthetic subset that resolves demonstrated
defects, while keeping the richer contract extensible and missing fields honest.

## Implementation increment — 2026-09-08

Both course tools now pass disclosed context through backend/suitability.py and
expose the assessment to the model and course cards. Selected exact synthetic
prerequisite statements have explicit necessary-condition/experience-route checks;
unmapped or missing statements remain unknown. Case-insensitive levels avoid
false exclusions. Filters run before result limiting, and model guidance requires
subject-mismatch alternatives to be qualified. Subject fit is still semantic, not
a structured discipline rule; absence claims remain scope-sensitive.

The seed-v2 synthetic ATAR convention is retained; generalized score-kind,
intake/cohort, verified qualifications, attendance requirements, coverage authority
and institutional access integration remain future work. No migration to real
admissions semantics is claimed. See EXP-LIVE-002/suitability-comparison.md for
actual rerun evidence and remaining response-quality limitations.
