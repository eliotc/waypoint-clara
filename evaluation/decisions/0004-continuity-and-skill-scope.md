# Decision 0004: Preserve reasoning alongside the work

Date: 2026-09-07. Status: continuity workflow authorized by Eliot; repository-local
skill placement is the implementation choice for this increment. No global skill
installation or cross-project policy is implied.

The owner wants to reconstruct early assumptions, evidence and changes of mind
without relying on weeks of conversation. The owner authorized the proposed
journey overview, dated learning checkpoints and linked decision records.

Keep a mutable current map in evaluation/journey/README.md and dated checkpoints
under evaluation/journey/checkpoints/. Accepted choices belong in decisions;
experiments retain hypotheses, immutable run evidence and review dispositions.
Retrospective entries state their provenance and gaps. Separate owner decisions,
AI recommendations, implementation choices and unresolved assumptions. Later
reversals get a follow-up/superseding record rather than erasing earlier rationale.

Procedure guidance for this workflow was kept in repository-local assistant skills,
without embedding product conclusions in them. Public edition: those skills are not
published ([Decision 0013](0013-publication-boundary.md)); this record and the
journey README describe the procedure. A report contains findings, not procedure.

Alternatives: a global skill today could apply Clara-specific assumptions to other
projects and evolve independently of the repo. Conversation or private memory alone
is hard to share and reconstruct. A current overview alone loses superseded thinking.
A checkpoint for every tool invocation would bury the meaningful decisions in noise.

Revisit extraction when a second project needs the same workflow. Extract only the
proven generic procedure to a shared package/global skill, pin its version, and keep
project rules and evidence here. Avoid maintaining conflicting local/global copies.

Limits: files are currently uncommitted. Git history begins when changes are
committed; retrospective checkpoints do not reconstruct nonexistent commits. Ignored
run evidence needs separate durable storage. This increment does not choose a backup
provider or publish private artifacts. See [CP-006](../journey/checkpoints/CP-006-continuity.md).
