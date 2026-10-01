# CP-009 — stronger uncertainty cues expose the limit of summary instructions

Recorded on: 2026-09-08. Provenance: contemporaneous. Author: Codex (AI-assisted).
Predecessor: [CP-008](CP-008-suitability-repair.md).
Sources: owner instruction to continue; comparison *(withheld)*.

## Before
Known mismatch filtering improved. Clara still omitted unknown eligibility when
speaking and sometimes invented nationality or lost unresolved questions in handover.

## Evidence and limitations
Added an explicit tool notice requiring a spoken eligibility caveat and prompt
rules against inferred personal attributes. 55 tests pass. Defined two supplementary
manual checks before rerunning the unchanged eight-session experiment; review queues
preserve their own rubric/trace hashes and do not rewrite baseline reports.
Run20260908T232255246073Z-949f3ecb:16 automated PASS,8 semantic NEEDS_HUMAN,0 errors.
Database contents unchanged. Manual review found caveats in9/10 recommendation turns,
no nationality invention in two contact summaries, and missing unresolved issues in
both summaries. This small sample cannot establish a population success rate.

## Changed thinking
A salient tool notice helps spoken qualification but does not guarantee follow-up
coverage. Longer summary instructions did not reliably preserve unresolved issues;
current completeness was worse than the one complete summary in the preceding run.
An explicit handover record with fact/evidence provenance is a better next design
hypothesis than another instruction-only increment. This is not yet tested.

## Dispositions
Implementation/rerun were authorized. New outcome acceptance remains for the owner.
Handover completeness and one spoken omission remain open; do not claim defects
closed based on passing transport checks or absence of nationality errors in two cases.

## Next and revisit trigger
Build and independently check a handover record retaining facts, corrections,
findings and open questions; keep actual transfer integration out of scope until
supported. Retain targeted follow-up uncertainty checks and revisit repetition
expectations explicitly if usability evidence warrants it.
