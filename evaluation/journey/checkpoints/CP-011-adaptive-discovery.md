# CP-011 — Adaptive personas expose specific false beliefs

Recorded: 2026-09-10; implementation/run Sep 9, review completed Sep 10.
Contemporaneous follow-up to [CP-010](CP-010-standalone-discovery.md).

## Before

Standalone discovery and visible limitations were the accepted direction.
EXP-SIM-001 interpreted supplied text; it did not interact with Clara. We proposed
student-owned recaps and adaptive conversations as a more realistic next probe.
The owner authorized that bounded increment (“go ahead,” then “continue pls”).

## Evidence

EXP-SIM-002 design *(withheld)* and
review *(withheld)*.
Run `20260909T092748157949Z-adaptive-1c8aab45`: four fresh local Live sessions,
20 user turns, four interpretations; eight deterministic checks passed and 28
semantic checks await owner review. Models: Gemini 2.5 Flash simulator and Gemini
3.1 Flash Live Preview Clara, existing read-only v2 dataset. Sixty tests passed.
The failed setup attempt is preserved separately; no model calls occurred there.
Usage-limit rejection delayed reading evidence, not the completed run itself.

## Changed thinking

A general caveat can coexist with a specific false belief. The returning student
assumed Online meant part-time; Clara did not correct it. The international
student adopted an unsupported qualification-conversion claim. The online-only
student received repeated campus suggestions despite a hard constraint, yet
found value in ruling out the institution. A recap also invented full-time work.
Positive synthetic usefulness is therefore not a quality score.

We extended the existing adapter with a transcript-only adaptive boundary and
added a bounded separately versioned runner, rather than relabeling scripted
assets. Requested recaps may use up to 120 words; ordinary replies retain the
50-word instruction. This resolves an instruction tension, but the run does not
establish consistent recap fidelity. No new owner acceptance of findings or
severity is inferred. Integrated handoff remains deferred.

## Next / unresolved

Propose targeted regressions and source-linked student facts/unknowns, correcting
specific assumptions before a further adaptive batch. Keep delivery, workload and
attendance separate. Real-user comprehension, UI attention, durable evidence
storage, and adoption remain untested. Ignored run artifacts require backup;
Git records this reasoning and implementation, not audio or private DB state.
