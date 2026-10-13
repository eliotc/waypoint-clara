# CP-025 — Calibration independence and retrieval provenance

Recorded on: 2026-10-10. Period covered: planning/code review on this date.
Provenance: contemporaneous inspection. Author: Codex, reviewer; also original author of the trust rubric, so not independent validation of all underlying criteria.
Predecessor: [CP-024](CP-024-lifecycle-pilot-assessment-gap.md).
Sources: [trust rubric](../../domains/education/trust-acceptance-v0.1.md), [CP-018](CP-018-persona-evaluation-learnings.md), [database snapshot implementation](../../local_database.py), [Live adapter](../../live_adapter.py), [record fingerprint](../../records.py). Detailed planning review is private and withheld under Decision 0013.

## Before

The next evaluation increment aims to calibrate judgment, preserve conditions and test the approved bounded demonstration. Known calibration examples and database snapshots provide useful foundations, but their limitations need to remain explicit when claiming unseen validation or a matched repair comparison.

## Evidence and limitations

- Rubric §5 explicitly labels its examples as known development/calibration data. Dividing those examples into new files does not establish that they were unused during development.
- `local_database.snapshot()` excludes embedding arrays and includes observation time. The existing record dataset fingerprint hashes the seed program. These are inspection facts; no database was queried or drift reproduced.
- The Live adapter timestamps received events and stores cumulative transcripts. This supports event-receipt chronology; alignment of particular spoken claims to tool availability is not independently established by those timestamps alone.
- CP-018 already distinguishes fixed scripts from adaptive conversations. The frozen benchmark's repeated scripts do not establish simulator fidelity or real-user understanding.
- No new model run, audio review, tests or performance measurements were performed. The 40-session acceptance result remains unestablished by this review.

## Changed thinking

Reviewer recommendations: keep known calibration cases as regression controls and validate generalization with new, separately controlled cases; preserve retrieval state across baseline and repair comparisons; distinguish structural coverage checks from semantic completeness; state the precise observable timing boundary. Simulator validity remains a separate research question from scripted repeatability.

These recommendations refine evidence claims, not the owner-approved severity rules or acceptance thresholds. They do not establish an application defect or invalidate every earlier conclusion.

## Dispositions

Code-inspection observations are recorded above. Proposed remediation belongs primarily to reusable harness provenance and domain evaluation case design. No new owner decision, run authorization, implementation or acceptance is recorded. Existing application ownership is unchanged.

## Next and revisit trigger

Specify canonical content/vector fingerprints and observation boundaries before a matched repair comparison. Record case exposure and source-family grouping before claiming held-out validation. Reconsider the timing limitation if a reviewed producer-to-consumer trace establishes the necessary causal ordering and claim alignment; reconsider retrieval uncertainty when immutable corpus vectors and query-generation configuration are preserved and verified. Use new evidence to append a follow-up rather than rewrite earlier records.
