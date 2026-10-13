# Decision 0014 — Gemini 3.8 Live as Clara's model

Date: 2026-10-01 (recorded 2026-10-08). Owner: Eliot. Status: Accepted and in production.

Clara's Live model is `gemini-3.8-live`, replacing `gemini-3.1-flash-live-preview`. The owner requested a trial revision on 2026-10-01, tested it and moved all production traffic to it the same day. Commit 1af6365 made it the deployment setting and code default, and updated the README and `.env.example`.

## Basis

The owner's own testing of the trial revision. Production logs from the first sessions showed no 1007, 1008 or 1011 errors. This was a light check of one or two sessions, not a measured acceptance result.

EXP-LIVE-005 (private, withheld from the public repository) ran both models on identical application code, prompt and synthetic data across 46 sessions. Independent review verified that every session completed with a consistent snapshot. It did not accept the report's behavioural comparison. This decision therefore does not rest on a claim that 3.8 is more trustworthy than 3.1.

## Consequences for evaluation

1. The trust benchmark ([Decision 0012](0012-trust-first-acceptance.md)) targets `gemini-3.8-live`. The benchmark freezes this exact model ID and records that a hosted model can change behind the same name.
2. Evidence produced on 3.1 stays labelled 3.1 and is not relabelled. This includes the trust family 1–3 pilot of 2026-09-27, the 3.1 arm of EXP-LIVE-005 and earlier showcase recordings. It remains useful for calibration and history, but it does not describe production behaviour.
3. Evaluation defaults and run instructions that still name 3.1 need updating before any run intended to describe production. This decision does not make those edits.

Simulator and judge model choices are separate and unchanged by this decision.

## Boundaries

This decision records a runtime configuration choice. It does not establish reliability, acceptance under the trust rubric or real-user suitability, and it does not authorize paid evaluation batches.

Primary owner: application runtime configuration. Related: [Decision 0008](0008-freeze-clara-baseline.md) (frozen baseline), [Decision 0012](0012-trust-first-acceptance.md) (trust acceptance).
