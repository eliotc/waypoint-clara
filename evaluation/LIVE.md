# Local Clara Live evaluation

This adapter connects to the real FastAPI → ADK → Gemini Live path. It sends
scripted **text**, receives PCM audio and transcripts, and captures tool calls,
results, cards and before/after database snapshots. It does not test microphone
recognition, browser playback/rendering or a generative student simulator.

The first experiment is **read-only**. PostgreSQL permissions block writes even
if the model attempts a booking. This is a documented difference from the demo
service: booking success, capacity and idempotency are not evaluated here.

## Prerequisites

- Python 3.11+, the application's `requirements.txt`, and `evaluation/requirements.txt`.
- Docker with Compose, or a local PostgreSQL server with pgvector and privileges
  to create databases and roles. The checked-in Compose file binds only loopback
  port 55432 and stores PostgreSQL data in temporary memory.
- Working Gemini credentials as used by the application. The server loads the
  project's `.env`; the fixture-only commands never do. Actual Live runs use API
  quota. Optional embedding preparation also calls the Gemini API.

Local PostgreSQL provisioning and two actual Gemini Live sessions were verified on
2026-09-06; see the baseline record below for results and limitations.

## Create an isolated database

From the repository root:

```bash
.venv/bin/python -m pip install -r requirements.txt -r evaluation/requirements.txt

docker compose -f evaluation/compose.yaml up -d --wait

.venv/bin/python -m evaluation.local_database create \
  --state evaluation/runs/local-db.json
```

This creates a new `waypoint_eval_<uuid>` database, applies the schema and seed,
rebases event dates to future days relative to the actual database clock, and
creates a separate SELECT-only reader role. It never seeds an existing database.
The reader's default transactions are read-only; marker identity and write
privileges are checked before serving. It does not use application DATABASE_URL.

`local-db.json` contains local credentials and a private evaluation token, is
created with mode 0600, and must stay in the ignored `evaluation/runs/` directory.
Do not commit it or include it in an experiment's input snapshot. If setup fails,
the state file remains for diagnosis; use a new path for a new attempt. Incomplete
provisioning may require removal of that exact generated database/role by the local
operator. The destroy command refuses unmarked databases rather than guessing.

If using an existing local pgvector server, set `EVAL_ADMIN_DATABASE_URL` to its
administrative DSN instead of starting Compose. Remote hosts, connection overrides
and production database names are rejected for evaluation connections. Local
proxies must not forward this service to shared infrastructure.

For course/knowledge/scholarship retrieval, create a **new** database with
`--with-embeddings`. This runs the actual seed embedding pipeline against that
new database. Without this flag, embedding-dependent tools fail explicitly; the
initial event/conversation experiment needs no embeddings. Event date rebasing
occurs after optional seeding. The runtime clock is real, not frozen; snapshots
record the actual event dates and observation times.

## Start Clara locally

In a separate terminal, from the same checkout:

```bash
.venv/bin/python -m evaluation.serve \
  --state evaluation/runs/local-db.json \
  --port 8765 \
  --model gemini-3.1-flash-live-preview
```

This wraps the existing app, binds `127.0.0.1`, uses the reader DSN, and requires the
private token on both HTTP and WebSocket requests. It does not publish or deploy
anything. Restart it after code or prompt changes: the adapter rejects a server
whose startup source hashes differ from the evaluating checkout.

## Run the Live baseline

```bash
.venv/bin/python -m evaluation validate evaluation/experiments/EXP-LIVE-001/config-v2.json

.venv/bin/python -m evaluation run evaluation/experiments/EXP-LIVE-001/config-v2.json \
  --state evaluation/runs/local-db.json
```

Validation performs no network/database calls. Execution checks the server model,
read-only mode, dataset marker and source identity before opening a fresh session
for each scenario. It consumes the greeting first, then sends one user message at
a time. It never retries interrupted sessions or actions; server retries become
an ERROR with preserved partial evidence.

Reports distinguish `live_text_input` from `synthetic_fixture`. Inspect statuses:
an intended Live run that cannot connect is ERROR, not evidence of model behavior.
Semantic checks remain NEEDS_HUMAN. Existing schema-1.0 fixtures continue working;
Live experiments use schema 1.1.

Each trace includes server metadata and actual database snapshots, client identity,
raw JSON event ordering, tool/result pairing and timing samples. Received audio
is stored as mono signed 16-bit little-endian PCM at 24 kHz; paths appear under
`observations.audio_files`. Timing measures first **received audio chunk**, not
first sound heard by a person. Numerical latency acceptance remains unapproved.
Partial traces/audio survive timeouts and protocol errors.

The adapter does not expose persona private facts or expected answers to Clara;
only the scenario's scripted user messages are sent. Cases are exploratory and
human-reviewed, not a calibrated measure of student decision quality.

## Stop and remove the local database

Stop the evaluation server with Ctrl-C first, then:

```bash
.venv/bin/python -m evaluation.local_database destroy \
  --state evaluation/runs/local-db.json

docker compose -f evaluation/compose.yaml down
```

The destroy command verifies the random ownership marker and drops only the named
DB/reader role, without FORCE or row-range deletion. Compose down discards all
state in this dedicated temporary PostgreSQL service. Preserve run reports before
removing private setup state.

## Remaining integration work

- Expand the completed DB-backed baseline to constrained course retrieval and repeated runs.
- Verify booking transactions, past-event handling, capacity and duplicate action
  behavior before introducing a write-enabled evaluation role.
- Add real audio input, interruption/reconnect scenarios, and browser rendering
  checks; current protocol tests do not establish end-to-end voice recovery.
- Add a persona simulator and structured review/comparison tooling.

## Verified local baseline — 2026-09-06

The first actual run is `20260906T104415869812Z-30726983`: two completed Live
sessions, six deterministic checks passed, two human checks pending. See
the review *(withheld)* for the registration-guidance
concern and inconsistent rebased event titles. The original report is unchanged.

On this workstation, PostgreSQL was provisioned without sudo by downloading and
extracting Ubuntu packages under the ignored `evaluation/runs/local-postgres/`.
It is a persistent user-owned cluster, unlike the tmpfs Compose option.
The prepared state is `evaluation/runs/local-db-20260906c.json`; it contains
credentials and must remain private. Two earlier failed provisioning attempts
remain separately recorded as `local-db-20260906.json` and `local-db-20260906b.json`.

To restart this already-prepared local cluster if stopped:

```bash
export LD_LIBRARY_PATH="$PWD/evaluation/runs/local-postgres/runtime/usr/lib/aarch64-linux-gnu"
evaluation/runs/local-postgres/runtime/usr/lib/postgresql/16/bin/pg_ctl \
  -D "$PWD/evaluation/runs/local-postgres/data" \
  -l "$PWD/evaluation/runs/local-postgres/server.log" \
  -o "-h 127.0.0.1 -p 55432 -k $PWD/evaluation/runs/local-postgres/socket" -w start
```

Then use the serve/run commands above with the prepared `local-db-20260906c.json`
state path. The extracted runtime is workstation-specific; Compose remains the
portable setup option. Stop Clara before stopping PostgreSQL:

```bash
evaluation/runs/local-postgres/runtime/usr/lib/postgresql/16/bin/pg_ctl \
  -D "$PWD/evaluation/runs/local-postgres/data" -m fast -w stop
```

A real database integration check can be included in the suite:

```bash
EVAL_TEST_STATE=evaluation/runs/local-db-20260906c.json make eval-test
```

It verifies both psycopg2 and asyncpg connection formats, database identity,
read-only enforcement and embedding completeness. All 43 checks passed locally.
Without `EVAL_TEST_STATE`, that integration check is explicitly skipped.


## Current fixture — 2026-09-07

The local evaluation server now uses `evaluation/runs/local-db-20260907-v2.json`
and database `waypoint_eval_794f24cb5d354350b817e69ffa2f2e1d` on the same port
55432. Use this state file with `config-v2.json` for subsequent runs. The earlier
state/database and recorded evidence remain available for historical inspection.

Version 2 gives events date-neutral titles/descriptions and preserves Melbourne
local start times and elapsed durations. Fixed intake years/deadlines in event
text are removed rather than replaced with invented admissions dates. This does
not rebase scholarship deadlines or knowledge documents; those retain seed facts.
The 37 corrected events have been checked against the old fixture for preserved
capacity, location, registration URLs and duration. All 45 tests passed, including
the real database integration check. No new model-behavior result is claimed.

## Adaptive persona conversations — 2026-09-09

EXP-SIM-002 *(withheld)* adds a separate bounded protocol
and CLI for Gemini 2.5 Flash personas choosing messages during actual local Clara
Live sessions. The adapter's scripted mode remains supported. This adaptive mode
exposes only transcripts to the simulator: no raw cards, UI, tools or DB snapshots.
It captures Live PCM but does not simulate hearing it. Consult the experiment for
commands, predeclared criteria, information boundaries and interpretation limits.
