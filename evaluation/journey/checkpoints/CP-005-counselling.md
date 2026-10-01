# CP-005 — Tool success is not recommendation suitability

Recorded on: 2026-09-07. Period covered: 2026-09-07.
Provenance: retrospective reconstruction. Author: Codex (AI-assisted).
Predecessor: [CP-004](CP-004-owner-correction.md).

Sources: EXP-LIVE-002 hypothesis *(withheld)*,
findings *(withheld)*,
review status *(withheld)*.
Run `20260907T014505755355Z-1e7c25e4`.

## Before
Test sufficient context, conflicting constraints, corrected preferences and human
contact, using real embeddings and two sessions per journey. Owner selected balanced
emphasis. Criteria were written before model execution.

## Evidence and limitations
Eight actual Live sessions/12 user turns completed; 16 automated checks passed,
eight semantic checks pending. Traces show postgraduate recommendations to school
leavers and an on-campus degree endorsed for an online-only student. Mode correction
and grounded contact retrieval worked in observed cases; summaries omitted unresolved
eligibility. Two repeats reveal examples, not a production failure-rate estimate.

## Changed thinking
Assess context retention, spoken advice, cards and handover summaries separately.
Code inspection indicates course tools omit relevant constraints and return names
without eligibility facts to Clara while sending fuller information to cards. This
is a supported contributing-cause inference, not a tested fix.

## Dispositions
Owner chose balanced coverage. AI recommendation: fix course-tool constraint handling
and model-visible prerequisite evidence, then repeat unchanged cases. Owner praise
was followed by a continuity discussion, not explicit adjudication of these findings
or approval of each proposed fix. No agent change was made during the experiment.

## Next and revisit trigger
Review findings and prioritize changes. Revisit causal explanations after a controlled
rerun. Version any decomposed rubric separately and regrade saved evidence so grader
changes do not masquerade as model improvements.
