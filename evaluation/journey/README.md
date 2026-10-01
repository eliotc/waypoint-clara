# Clara learning journey

Updated: 2026-09-27. This is the current map; dated checkpoints preserve earlier
thinking. Start here when resuming an evaluation increment, then follow the links
relevant to the question. Operational setup lives in [LIVE.md](../LIVE.md).

Public edition: items marked *(withheld)* refer to experiment evidence, records, planning
material, assistant tooling or broader platform plans kept outside the public repository under [Decision 0013](../decisions/0013-publication-boundary.md).

## Purpose and current understanding

Clara is an agile demonstration for building confidence in adopting agents
through evaluation. The goal is justified confidence in useful
behavior, not merely a compelling conversation or a high test score. Eliot is the
current demo product owner and domain decision-maker. The selected synthetic
database is factual authority within an experiment, not proof of real-world truth.

We have progressed from an offline evidence harness to real local Live sessions,
then to repeated counselling journeys. The latest experiment exposed eligibility
and study-mode mismatches despite successful transport and tool execution.
Conversation context, spoken advice, cards and handover summaries need distinct
assessment. The owner accepted the demonstrated defect categories on Sep 8; a bounded repair
and controlled rerun followed. Spoken uncertainty and handover fidelity remain unresolved.

## Timeline — rewind from here

| Checkpoint | Period covered | Change in understanding |
|---|---|---|
| [CP-001](checkpoints/CP-001-foundation.md) | Early discussion through Sep 6 | Skills guide work; executable experiments preserve evidence independently |
| [CP-002](checkpoints/CP-002-behavior-contract.md) | Sep 6 | Define provisional successful behavior before measuring it |
| [CP-003](checkpoints/CP-003-live-baseline.md) | Sep 6 | Actual Live path works; automated checks leave semantic questions open |
| [CP-004](checkpoints/CP-004-owner-correction.md) | Sep 7 | Owner corrects registration interpretation; fixture defect remains valid |
| [CP-005](checkpoints/CP-005-counselling.md) | Sep 7 | Correct tool execution does not establish suitable recommendations |
| [CP-006](checkpoints/CP-006-continuity.md) | Sep 7 | Preserve the evolution of reasoning as a first-class project record |
| [CP-007](checkpoints/CP-007-institutional-foundation.md) | Sep 8 | Accept defects; distinguish advice from assessment; begin Git history |
| [CP-008](checkpoints/CP-008-suitability-repair.md) | Sep 8 | Block known mismatches; spoken uncertainty and handover remain inconsistent |
| [CP-009](checkpoints/CP-009-spoken-fidelity.md) | Sep 8 | Spoken caveats improve; unresolved handover issues still disappear |
| [CP-010](checkpoints/CP-010-standalone-discovery.md) | Sep 9 | Defer integrated handoff; test standalone value and visible limitations |
| [CP-011](checkpoints/CP-011-adaptive-discovery.md) | Sep 9–10 | Adaptive dialogue exposes false beliefs despite general caveats |
| [CP-012](checkpoints/CP-012-honest-stopping.md) | Sep 10 | Honest no-match outcomes need not manufacture a next step |
| [CP-013](checkpoints/CP-013-repair-checkpoint.md) | Sep 10 | Repairs under regression; simulator comparison prepared, not run |
| [CP-014](checkpoints/CP-014-sim-comparison.md) | Sep 10 | Completed EXP-LIVE-003 audit, froze baseline, executed EXP-SIM-003 model comparison |
| [CP-015](checkpoints/CP-015-independent-baseline-audit.md) | Sep 15 | Independent baseline audit of Clara capabilities |
| [CP-016](checkpoints/CP-016-bounded-repair-audit.md) | Sep 15 | Bounded repair audit and experience guard repair |
| [CP-017](checkpoints/CP-017-live38-ordinary-pilot.md) | Sep 16 | Gemini Live 3.8 ordinary pilot execution |
| [CP-018](checkpoints/CP-018-persona-evaluation-learnings.md) | Sep 21 | Persona evaluation learnings and multi-turn student recaps |
| CP-019 *(withheld)* | Sep 22 | Evaluator comparison pilot: typed decisions still need semantic calibration |
| [CP-020](checkpoints/CP-020-contextual-scope-adjudication.md) | Sep 22 | Decision 0011 contextual scope adjudication on C15 |
| CP-021 *(withheld)* | Sep 22 | Tiered evaluation: deterministic checks first, escalation for consequential or uncertain claims |

CP-001–005 are retrospective reconstructions written Sep 7, not contemporaneous
notes. Their sources and limitations are recorded individually. CP-006–014 are contemporaneous checkpoints. No earlier Git commits or precise conversation timestamps have
been fabricated. The initial accumulated foundation and CP-001–006 were committed as `913859f`
on Sep 8. Earlier checkpoints are retrospective documents within that commit.

## Decisions, proposals and open questions

Accepted: [repository foundation](../decisions/0001-foundation.md),
[provisional behavior rules](../decisions/0002-provisional-behavior.md),
[mixed-event offer interpretation](../decisions/0003-mixed-event-registration.md),
[continuity method](../decisions/0004-continuity-and-skill-scope.md),
[counselling defect categories](../decisions/0005-counselling-defects.md),
[standalone discovery scope](../decisions/0006-standalone-discovery.md),
[honest no-match outcomes](../decisions/0007-honest-no-match.md),
[baseline freeze](../decisions/0008-freeze-clara-baseline.md).
An honest stopping point is acceptable when no useful supported next step is available; do not manufacture an action to satisfy the rubric.

Implemented: bounded course-tool suitability checks, model/card eligibility facts
and handover instructions. A controlled rerun demonstrates improvement but leaves
spoken uncertainty and fact-faithful handover issues; see comparison *(withheld)*. The [proposed data contract](../domains/education/suitability-foundation.md)
is grounded in [institutional desk research](../research/2026-09-08-institutional-counselling.md).
The owner accepted the defect categories, not every detailed schema field or a
blanket pass/fail disposition of all repetitions. Broader rule semantics and consistent response quality remain outstanding. The
fidelity follow-up *(withheld)* adds explicit
spoken notices: caveats improve, but both handover summaries omit unresolved issues.
The owner subsequently deferred integrated handoff to test standalone discovery.
The adaptive follow-up *(withheld)* now exercises student recaps in four actual Live conversations. It exposes unsupported beliefs, invented facts and conflicting next steps despite general caveats. Next proposal: targeted regressions and source-linked student facts/unknowns before another adaptive batch. See the
initial persona pilot *(withheld)*. Human contact remains
available; the prior handover defects are not retroactively resolved.

Still open: detailed institutional data/access validation; sufficient versus
repetitive clarification; handover completeness; latency targets; severity/release
gates; audio input/recovery; booking integrity; simulator validity; portability
beyond education; durable storage of ignored run evidence. The earlier clarification
check remains proposed acceptable, not explicitly accepted.

## Current execution checkpoint

See [CP-016](checkpoints/CP-016-bounded-repair-audit.md), recorded September 15.
The inherited bounded-repair run completed. Application guidance, recap preservation
and explicit stopping improve; busy attendance and international procedure defects
remain. Independent offline probes exposed four experience-guard failures. See the
review and next handoff *(withheld)*.
Fix guard correctness before another broad Live run. No all-pass acceptance or
deployment is recommended. Earlier sections describe historical stages.

## Planned model comparison

[Gemini 3.8 Live roadmap](../plans/gemini-3-8-live-comparison.md), captured September 15:
finish guard review, compare standard Live first, then evaluate Extended Thinking
separately with correct asynchronous completion handling. This is planned work,
not a model switch, executed experiment or deployment approval.

## Continue the record

Use the [checkpoint template](checkpoint-template.md) at meaningful learning or
decision boundaries, not for every tool call. Add the checkpoint to this index
and update the current understanding. A checkpoint can legitimately record no
new decision. Link to source evidence instead of copying whole traces.

Published checkpoints preserve the understanding at that time. Add a follow-up
checkpoint or dated correction for changed interpretation. For changed accepted
decisions, create a superseding decision that names the predecessor and rationale;
keep the predecessor readable. Minor typo/link fixes may be edited directly.
Experiment reports remain immutable. Procedure guidance lived in repository-local
assistant skills, which are not published; accumulated product conclusions belong
in the journey and decisions.

To rewind: select a checkpoint, read its “Before / Evidence / Changed thinking,”
then follow the decision and experiment/run IDs. Git history can recover versions
once committed. Ignored `evaluation/runs/` artifacts require separate backup;
Git preserves these reasoning records, not the underlying audio or private state.
If evidence is unavailable, retain its ID and mark that limit rather than recreate
or imply access. Do not copy private DB credentials into checkpoints.

## 2026-09-16 — Ordinary-journey pilot on Gemini 3.8 Live

Owner authorized this bounded exploration despite documented parser edge cases. See [CP-017-live38-ordinary-pilot](checkpoints/CP-017-live38-ordinary-pilot.md) and pilot review *(withheld)*. Four sessions completed; conversation findings remain. The earlier guard-first roadmap is not a claim this pilot was blocked or that defects are now accepted.


### Public showcase: an evolving student decision
Journey v2 *(withheld)* records the owner-requested shift from a two-turn transport example to six fixed questions with visible progress and outcome-first findings. Implementation verified offline; live story quality remains unverified.

## 2026-09-21 — Persona evaluation and model-comparison learnings

[CP-018](checkpoints/CP-018-persona-evaluation-learnings.md) captures valid alternative
tool paths, fixed-script limitations, guard versus model effects, unknown eligibility
versus no options, and evaluator coverage gaps. The bounded 3.8 run is mixed evidence,
not upgrade acceptance. Earlier execution summaries above describe historical stages.

## 2026-09-22 — Shadow evaluator pilot

A 24-case pilot compared automated claim-level judges against provisional reference
labels (checkpoint and report *(withheld)*: vendor comparison). Typed decisions were fast,
but the judges shared consequential misses and the labels were provisional. Shadow
use only; no automatic acceptance gate or application change.

## 2026-09-22 — Contextual-scope adjudication

[CP-020](checkpoints/CP-020-contextual-scope-adjudication.md) supersedes the
provisional C15 defect interpretation: the owner accepted its course-specific
scope. C14 remains unsupported under Decision 0010. Judge agreement was recomputed
separately against the revised references; original outputs remain unchanged.

## 2026-09-22 — Tiered evaluation direction

The owner accepted a tiered direction for evaluating Clara: deterministic checks
(citation validity, chronology, schema) constrain first; automated judges classify
individual claims; stronger models or people review flagged, uncertain or
release-critical cases. No automated judge holds release authority. Post-turn
audit findings feed the improvement backlog and never alter a live conversation.
The detailed checkpoint and related planning material are *(withheld)*.

## 2026-09-27 — Evaluation record storage boundary

[CP-022](checkpoints/CP-022-evaluation-record-storage-boundary.md) records the
separate PostgreSQL import proof, an existing dangling verification reference,
and the need to keep superseded assessments for audit while excluding them from
current-outcome trends. This is a local harness slice, not a public history API.

## 2026-09-27 — Trust acceptance before expanding the benchmark

[CP-023](checkpoints/CP-023-trust-acceptance-boundary.md) records the owner's priorities: honest capabilities, grounded advice and consistency. The [trust acceptance rubric v0.1](../domains/education/trust-acceptance-v0.1.md) supplies calibration examples and gates for demonstration (Bucket A), restricted use (Bucket B) or non-acceptance (Bucket C). Thresholds and benchmark protocol were approved by the owner and frozen on 2026-09-27 following independent review; current model performance has not been accepted.

## 2026-09-27 — Lifecycle pilot assessment gap

[CP-024](checkpoints/CP-024-lifecycle-pilot-assessment-gap.md) records a completed
three-session transport pilot whose authored all-pass assessments missed material
claims. Stored results require accurate reviewer provenance and separately preserved regrades.
