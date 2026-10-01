# Conversation quality pack — v0.1

Status: draft for review. Owner requested an isolated reusable pack alongside
ongoing Clara work. No runs, model changes or application changes are made here.
The criteria are proposed operationalisations of the current behaviour contract,
not a newly approved release gate. These files are design assets, not runnable
experiment configuration; do not feed criteria.json directly to the runner.

## Scope

Four portable criteria live once in [criteria.json](criteria.json): need clarification,
clarity/relevance, grounding/uncertainty, context/boundaries. Domain authorities and
examples stay in domain packages. First binding:
[education eight-case matrix](../../domains/education/packs/conversation-quality-v0.1.md).
All examples are independently synthetic course-discovery cases, not human research
records. Link/video/product recommendation, financial calculations, handoff selection,
audio perception and real-user trust are excluded from this first pack.

## Hypothesis and counterevidence

A shared rubric plus domain-specific references can identify conversational failures
without teaching the harness business rules. Paired cases exercise question clarity,
knowledge, available evidence and corrections. Failure of this design includes
reviewers needing undocumented assumptions, inconsistent dispositions on acceptable
controls, or inability to separate target behaviour from missing evidence. No causal
or population claim follows from eight synthetic cases.

## Ownership and isolation

- Application: Clara instructions, retrieval and state handling; existing guard
  repairs retain their own tests and acceptance work.
- Domain package: input turns, synthetic facts and correct reference interpretation.
- Harness: execution, trace capture and result handling; no new custom parser or
  runner is introduced for this pack.

Keep EXP-LIVE-003 and EXP-SIM-003 reports, configs and rubrics unchanged. This pack
is not a substitute for their outstanding checks or guard review. A later experiment
may compose these assets once approved and supported by the runner.

## Review protocol

Judge each criterion separately with exact turn/source references: PASS, FAIL or
NEEDS_HUMAN for unresolved semantic evidence; execution errors remain ERROR.
Not-applicable dimensions are excluded with a reason, not counted as passing.
Inspect all turns; a correct recap does not erase an earlier unsupported assertion.
No overall pass percentage, severity weights or release thresholds are set yet.

The evaluator sees domain authority and traces. The application sees only ordinary
user inputs. Future simulators see their profile and visible conversation, never
the answer key or rubric. Proposed/effective tool values and spoken claims remain
separate observations. Synthetic usefulness is not measured human comprehension.

## Later pilot, pending review

After independent guard review, create a new schema-valid experiment using the
existing read-only Clara adapter. Proposed first smoke batch: eight cases, one fresh
session per case, at most two scripted user turns each (16 turns). This bounds cost,
not statistical confidence. Confirm current sources/model and budget before launch.
Run the fixed cases before adaptive personas. Keep paired cases adjacent and reverse
A/B order in a later repetition; record source/model/config versions and failures.
If source facts differ from the matrix preconditions, revise the design or mark the
case blocked rather than manufacture expected answers. Compare fixes on identical
criteria; reserve fresh paraphrases for later independent checks.

Immediate next step: review eight cases and source bindings, then author/validate
the separate experiment config. No scheduler or continuous execution yet.

## Executable binding prepared

The owner accepted the eight-case matrix. EXP-CQ-001 *(withheld)*
now supplies schema-validated scenarios/personas and a draft configuration using
the existing adapter: eight sessions, 12 scripted turns. No runs performed.
The design criteria file remains non-executable; use the experiment config for
validation. Guard acceptance and source/configuration preflight remain outstanding.
