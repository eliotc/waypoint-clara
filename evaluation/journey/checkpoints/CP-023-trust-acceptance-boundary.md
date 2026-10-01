# CP-023 — Freeze trust criteria before measuring Clara's operating range

Recorded on: 2026-09-27. Provenance: contemporaneous. Author: Codex, rubric designer.
Predecessor: [CP-022](CP-022-evaluation-record-storage-boundary.md).
Sources: owner discussion of non-determinism and trust priorities; run showcase-e51d449f444cb241; [Decision 0012](../../decisions/0012-trust-first-acceptance.md).

## Before

Repeated tool-policy adjustments risked making success depend on accommodating each new model path. An earlier recommendation to expand adaptive personas did not first establish a stable acceptance boundary.

## Evidence and limitations

The September 27 run retrieved application guidance in Q2, reused it correctly in Q5 and contradicted that history in Q6. The per-turn tool policy flagged Q2 and Q5, while the automated semantic evaluation returned four generic fallbacks. These observations separate an overly restrictive grader, a real consistency defect and an incomplete assessment.

Existing adaptive experiments already exist; adaptive personas are not a newly invented next capability. Before expansion, acceptance criteria need to establish what repeated runs should measure.

The owner prioritizes honest abilities, grounded responses and avoidance of contradictions. Synthetic catalogue fidelity does not establish real-institution accuracy or real-user trust.

## Changed thinking

Freeze the outcome requirements and calibrate the grader before measuring variability. Legitimate evidence reuse should pass across tool paths. Material contradictions must remain failures even when a model exhibits them repeatedly. Distinguish Clara's combined solution limits from Gemini's intrinsic limits.

## Dispositions

Owner priorities are recorded in Decision 0012.
Codex delivered [rubric v0.1](../../domains/education/trust-acceptance-v0.1.md), including historical examples, authored controls, severity definitions and three acceptance buckets.
Hermes completed an independent review of the criteria, calibration labels and thresholds ([receipt](../../domains/education/trust-acceptance-v0.1-hermes-review.md)), recommending approval. Eliot approved the severity rules, numerical acceptance gates (Bucket A/B/C) and 40-session benchmark protocol on 2026-09-27, formally freezing rubric v0.1.

## Next and revisit trigger

Prepare the executable benchmark assets (scenarios, personas, schedules) and map the T1–T3 criteria into the evaluation harness/judge prompt. Calibrate the automated grader against the calibration controls before running the 40-session benchmark batch. Permit bounded repairs without continuously weakening criteria. Revisit the rubric only for independently justified ambiguity or new product scope, and version/regrade affected evidence.
