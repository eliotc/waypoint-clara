# Decision 0005: Accept counselling defects and establish the repair foundation

Date: 2026-09-08. Owner: Eliot. Status: accepted defect categories and direction
 to establish foundations for addressing them; detailed data contract is proposed.

Source: owner statement in this conversation, “I agree that those are defects,
and we need to establish the foundations to address them,” followed by a request
for a reality check of institutional digital/human counselling data access.

Accepted issues: unqualified recommendations that conflict with disclosed prior
qualifications; on-campus recommendations presented as suitable for online-only
students; omission of material qualification gaps and unresolved eligibility in
handover summaries. Evidence is in EXP-LIVE-002 findings *(withheld)*.
This records acceptance of demonstrated defect categories, not a blanket FAIL for
every whole scenario or rejection of correct behavior within those scenarios.

Establish the data and evidence foundation before the next runtime fix. The owner
also authorized starting Git check-ins. The initial foundation/history is committed
as `913859f`; no push or deployment was requested or performed.

Research finding that qualifies the implementation: real course advice involves
more than an ATAR cutoff; distinguish guidance from formal assessment, delivery
from study load, and historical selection ranks from hard minimums. Internal staff
system permissions remain institution-specific and unverified by desk research.
See [research](../research/2026-09-08-institutional-counselling.md) and
[proposed contract](../domains/education/suitability-foundation.md).

The implementation must preserve unknown eligibility rather than equating null
requirements with eligibility or excluding all postgraduate routes universally.
Detailed field choices and migrations are proposals pending implementation review;
existing synthetic data/runs have not been relabeled as real institutional policy.
No new acceptance is inferred for the earlier isolated clarification check.

Revisit with an institution's SME walkthrough or evidence that a particular rule
has different semantics. Verify fixes through deterministic cases and a new Live
run; preserve baseline reports and separate changed data/rubrics from model effects.
