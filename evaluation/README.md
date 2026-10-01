# Evaluation foundation

Public edition: references marked *(withheld)* point to experiment evidence, records or planning material kept outside the public repository under [Decision 0013](decisions/0013-publication-boundary.md).

Clara is the first use case for an evaluation workflow designed to be reusable
beyond this domain. This foundation implements versioned assets, offline
trace evaluation, evidence preservation and conservative result handling. A
localhost-only, read-only Clara Live adapter is also available; see [LIVE.md](LIVE.md).

**The bundled experiment replays hand-authored synthetic traces. It does not run
Clara, call a model, connect to a database or establish real student outcomes.**

For current direction and the history of our reasoning, start with the
[journey overview](journey/README.md). It links dated learning checkpoints, owner
decisions, evidence and unresolved proposals.

For code ownership and repair routing, use the [three-layer map](architecture.md)
and [finding template](finding-template.md). The current toolkit still contains
Clara-specific integrations; the map identifies these explicitly.

## Start here

From the repository root, using Python 3.11 or later:

```bash
.venv/bin/python -m pip install -r evaluation/requirements.txt
make eval-validate
make eval-test
.venv/bin/python -m evaluation run evaluation/experiments/EXP-000/config.json
```

The final command intentionally exits **2**: one scenario passes its narrow
deterministic checks; the other needs human judgment about the response's
usefulness. This demonstrates honest incompleteness, not a broken installation.
`make eval-fixture` invokes the same command (Make also exits nonzero).

Each run prints its report location under `evaluation/runs/<run-id>/`:

- `manifest.json`: evidence kind, reference model, toolkit/environment metadata,
  Git revision/dirty state and hashes of the exact referenced assets.
- `inputs/`: content-addressed copies of those inputs and toolkit source.
- `trace-*.json`: user turns, responses, tool arguments/results, cards and observations.
- `report.json`: per-check results, severity, evidence pointers and case totals.
- `summary.md`: readable overview with an explicit fixture-only qualification.

Runs never overwrite prior results. The reference model names the intended
future target; `target.model` is null because no model runs in fixture mode.
Repeating a fixture only checks harness consistency, not model variability.

## The working loop

1. **Explore needs:** interview personas; label source provenance and synthetic
   assumptions. Preserve criticism and uncertainty, not just positive reactions.
2. **Define an experiment:** record a hypothesis, fixed conditions, alternatives,
   observable criteria and proposed severity before running it.
3. **Exercise the system:** preserve the participant-visible experience and the
   independent evaluator's evidence. Keep these information channels separate.
4. **Review evidence:** distinguish product defects, simulator drift, missing
   evidence and grader errors. Review semantic judgments against source facts.
5. **Decide:** record what the owner accepts, rejects or wants to investigate.
6. **Improve and retest:** turn demonstrated failures into regression cases;
   compare with the preserved baseline using the same criteria and inputs.

See [the first experiment](experiments/EXP-000/hypothesis.md),
[the provisional education contract](domains/education/contract.md), and
[the architecture decision](decisions/0001-foundation.md).

## Asset and execution contracts

`schemas/v1.json` and `schemas/v1.1.json` use JSON Schema 2020-12.
Version 1.0 preserves the offline format; 1.1 adds Live target configuration and evidence kind. The CLI validates the schema plus
cross-file references, unique case/check IDs, fixture coverage and user-turn
agreement. References are relative to the containing experiment or scenario.
Inputs must resolve within this repository. New incompatible formats require a
new version and migration rather than silent reinterpretation.

| Asset | Responsibility |
|---|---|
| Experiment | Owner, hypothesis, domain, dataset, target, cases and repetition count |
| Persona | Source provenance, fixed personal facts, goals and disclosure policy |
| Scenario | User task, turns and explicit checks tied to criteria and severity |
| Dataset | Authority for this experiment, fixed reference clock and fixture data |
| Trace | Observed interaction, tool evidence, cards and optional state observations |
| Report | Check results and scenario outcomes; evidence kind cannot be omitted |

The first grader supports exact typed equality at JSON Pointers and manual
review. `/turns/0/tools/0/arguments/student_atar`, for example, points to a concrete
argument. Equality checks do not establish semantic correctness. Missing evidence
is an error, and a completed turn with empty assistant text fails independently
of other checks. The trace format represents completed user interactions, not
every intermediate silent tool-calling event.

| Status | Meaning |
|---|---|
| PASS | All specified checks passed; no claim beyond their scope |
| FAIL | An observed result violates a specified requirement |
| NEEDS_HUMAN | Evidence exists but a judgment remains unresolved |
| ERROR | Execution, validation or required evidence is incomplete |
| SKIPPED | Requested work was not executed; reserved for future adapters |

CLI exit codes: `0` all checks passed; `1` completed with failures; `2` error,
skipped work or pending review. An empty run cannot pass. Per-check results remain
visible even when a case has both an error and a failure. These are completion
signals, not production release gates. No release-severity policy is approved yet.

Manual review should be recorded in the experiment's `decision.md`, citing run ID,
case, check, reviewer, disposition and rationale. Do not edit an original report
to turn pending reviews into passes. A machine-readable review/compare command is
a later increment.

## Assistant guidance and portability

Repository-local assistant skills guided the design, running and review of
experiments; they are not published ([Decision 0013](decisions/0013-publication-boundary.md)).
Definitions live in the shared assets, not in assistant prompts. All executable entry
points work independently of a coding assistant.

`adapters.py` defines the interaction boundary. `FixtureAdapter` replays synthetic
traces. `live_adapter.py` connects to the actual Clara WebSocket service through a
private local evaluation wrapper. It captures text-input Live output, tool traces,
PCM and full cards. See [LIVE.md](LIVE.md) for isolated database setup and the
explicit read-only limitation. Database preparation and two actual Gemini Live sessions were verified on
2026-09-06; see the EXP-LIVE-001 decision record for results and limitations. Another domain can implement the same boundary without education rules
entering the shared runner.

## Legacy suites

The existing `eval_suite.py` and `testing/red-team/run_regression.py` remain
separate text-proxy/direct-tool suites. Their reports use `legacy-1`, not this
foundation's schema. They now reject empty/incomplete success and use unique
report paths. The regression runner defers SDK imports and retains tool arguments
and results; semantic regex judgments require review. Earlier saved reports have
not been rescored and must not be treated as current results.

Both DB-using entry points require **EVAL_DATABASE_URL** pointing to a separately
provisioned disposable PostgreSQL database, seeded for that run. They refuse the
application DB's same host/port/database even under different credentials. This
guard cannot detect different proxies/aliases to the same database; provisioning
is still the operator's responsibility. Do not point it at production.

An isolated local database with real embeddings has been provisioned and exercised. The new
`evaluation.local_database` command can provision a dedicated local database; its
Live wrapper uses only the reader role. Legacy write tests still require a separate
operator-managed disposable setup and are not covered by the read-only Live run. The legacy tests still
have date-dependent expectations and can insert rows/decrement event capacity.
Discard the disposable database after a run, including failed runs. The old
high-water-mark cleanup was removed because it could delete unrelated rows and
did not restore capacity. Never reseed or clean a shared database as test cleanup.

## Evidence and change management

Commit code, synthetic fixtures, hypotheses and reviewed findings. Keep
generated runs out of Git and container images. Real interviews/audio require
appropriate access controls; this toolkit does not yet redact sensitive content.
The input snapshots are restricted to referenced assets, not a copy of the repo
or environment. Store private/large evidence in controlled artifact storage before
using real participants.

Keep short-lived implementation branches, merge useful increments, and retain
experiment IDs/configurations. A changed grader or rubric warrants regrading the
same preserved evidence; record that separately from a changed agent. Keep
exploratory cases separate from held-out evaluations once model tuning starts.

## Next increments

1. Measure compliance with the [agreed provisional rules](domains/education/contract.md).
   Local prompt/manual alignment completed 2026-09-06; Live validation remains pending.
   Refine clarification quality and latency targets through evidence.
2. Expand the completed read-only Live baseline to constrained course retrieval and repeated runs.
3. Verify booking capacity/idempotency before write-enabled tests; card routing now
   uses per-connection context and has concurrent/threaded component tests.
4. Persona interview/simulation runner and the explanation-variant experiment.
5. Structured review dispositions and compatible-run comparisons.

The initial foundation was offline only. A subsequent local prompt/manual alignment
applied the agreed behavior contract without deploying or changing production tools.
The next increment adds a read-only Live adapter and per-connection card routing.
End-to-end card/session isolation and booking integrity still require DB-backed
validation; write-enabled Live tests are not included.

## Adaptive pilot

EXP-SIM-002 *(withheld)* implements bounded, transcript-only
persona conversations against local Clara, followed by an explicitly elicited
student recap and persona interpretation. Its dedicated schema and CLI preserve
protocol 2 separately from the scripted v1/v1.1 runner. Generated conversations
remain exploratory; the database/tool evidence is available to the reviewer, not
the simulator. See the experiment's decision record for actual outcomes.

## Isolated evaluation packs

[Conversation quality v0.1](packs/conversation-quality-v0.1/README.md) is a draft
reusable rubric with an eight-case education binding. It does not alter existing
experiments and has not been executed.
