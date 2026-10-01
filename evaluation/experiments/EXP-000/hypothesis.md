# EXP-000: Validate the evaluation foundation

This experiment tests the harness, not Clara. All input interactions were authored
as fixtures. No simulated interview or live-model run has occurred.

Hypothesis: a correctly implemented harness can retain concrete constraint and
tool evidence, detect violations, and leave semantic quality unresolved for review.

Fixed conditions: `education-harness-v1` fixture, clock 2026-09-06 UTC, two short
scripted interactions, one repetition, no model and no database connection.

Expected result: `gate-001` passes its narrow no-tool check; `constraints-001`
passes its exact argument/card checks and remains NEEDS_HUMAN for decision support.
The CLI should exit 2. This is not a recommendation-quality score.

Counterexamples covered in the harness tests: incorrect ATAR, absent tool evidence,
empty answer, invalid schema, duplicate case, model/tool fault and repeated runs
overwriting evidence. Changing any of these must not produce a false all-pass result.
