# CP-016 — Bounded repairs and experience-guard counterexamples

Recorded: 2026-09-15. Reviewer: Codex. Contemporaneous follow-up to
[CP-015](CP-015-independent-baseline-audit.md).

## Before
Hermes implemented bounded repairs and left a Live run active after exhausting
its iteration budget. Offline tests were reported passing; Live acceptance pending.

## Evidence and limitations
Independent review *(withheld)*
records completion of run 20260915T103056655339Z-e2dc4f6f: 22 turns, matching backend
hashes, 10 transport/isolation passes. No new run launched. Local text-input evidence
and direct offline resolver probes do not establish production outcomes.

## Changed thinking
Application guidance, recap facts and explicit stopping improve. Busy attendance
and international procedure errors persist. Four new deterministic counterexamples
show the experience guard itself creates unsupported positive values. Passing tests
and a convincing evidence label do not establish evidence extraction correctness.

## Dispositions
Analyst recommendation: do not accept an all-pass baseline or deploy these repairs.
No new owner decision. Fix resolver correctness before more broad paid evaluation.

## Next
Use the review's bounded handoff and saved counterexamples; retain successful cases
and add the still-missing positive controls. Revisit after repaired guard evidence
and focused dialogue checks.
