# CP-003 — A working Live path still leaves product judgment

Recorded on: 2026-09-07. Period covered: 2026-09-06.
Provenance: retrospective reconstruction. Author: Codex (AI-assisted).
Predecessor: [CP-002](CP-002-behavior-contract.md).

Sources: EXP-LIVE-001 review *(withheld)*,
[LIVE setup](../../LIVE.md). Run `20260906T104415869812Z-30726983`.

## Before
The foundation had offline/protocol checks but no verified local database-backed
Live execution. The goal was a real baseline with inspectable evidence.

## Evidence and limitations
A user-owned PostgreSQL/pgvector runtime was prepared without Docker, with Gemini
embeddings. A psycopg/asyncpg connection-format mismatch was fixed. Two actual Live
sessions completed: six automated checks passed, two semantic checks pending.
Inputs were text; audio was received, not independently judged for intelligibility.

## Changed thinking
The local path can capture model, tool, card and database evidence. That does not
establish counselling quality. Initial AI review questioned a general registration
offer around walk-in events and separately found title/date inconsistencies caused
by evaluation date rebasing. The first concern was a review interpretation awaiting
owner input, not an accepted defect. Later owner correction is in CP-004.

## Dispositions
Implementation choices: user-owned runtime and read-only DB role. AI recommendation:
clarification response appears acceptable; examine registration ambiguity and fix
fixture dates. No owner acceptance of those semantic judgments was recorded then.

## Next and revisit trigger
Obtain owner interpretation and correct demonstrated fixture defects. Reassess local
parity when browser/audio-input, write actions and deployed infrastructure are tested.
