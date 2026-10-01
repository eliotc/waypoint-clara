# Evaluation record store: PostgreSQL schema

This is a **query and audit projection** of the JSON records in `evaluation/records/`. The JSON files are the source of truth; PostgreSQL supports trend queries, analysis, and internal UI review tooling.

In this public repository, operational records are not published ([Decision 0013](../decisions/0013-publication-boundary.md)): `evaluation/records/` is git-ignored because the showcase runner writes records there at runtime. Tests use labelled synthetic fixtures under `evaluation/tests/fixtures/records/`.

The schema lives inside the `waypoint` database under `SCHEMA evaluation`, completely separated from Kingsford University course tables (`public.*`).

`0001_records.sql` provisions:
- Five core record tables: `eval_runs`, `eval_assessments`, `eval_issues`, `eval_results`, and `eval_verification_events`.
- `evaluation.current_assessments`: detailed view including JSONB payloads; for internal triage and review.
- `evaluation.public_assessment_summaries`: sanitized summary view exposing only metadata and denominator counts (passes, issues, incomplete, model, timestamps) with no raw dialogue payloads or evidence quotes.
- Three NOLOGIN group roles:
  - `waypoint_eval_record_writer`: `SELECT, INSERT` on evaluation schema only. Strictly no `UPDATE` or `DELETE`. No write access to application tables.
  - `waypoint_eval_record_reader`: `SELECT` on all evaluation schema tables and views (internal triage).
  - `waypoint_eval_public_reader`: `SELECT` on `evaluation.public_assessment_summaries` only.

Set `EVAL_RECORDS_DATABASE_URL` in `.env` pointing to a login role granted `waypoint_eval_record_writer`, then import:

```sh
.venv/bin/python -m evaluation.postgres_records evaluation/records
```

The importer validates the versioned schema, cross-record foreign keys, and denominators before insertion. It executes in one transaction, accepts identical re-runs idempotently, and rejects changed payloads under existing IDs. The JSON filesystem writer in `evaluation/records.py` is likewise hardened with an immutability guard.

Role-privilege checks in `evaluation/tests/test_postgres_records.py` are opt-in and never read `.env` or the application `DATABASE_URL`: set `RUN_EVAL_DB_ROLE_TESTS=1` and `EVAL_ROLE_TEST_DATABASE_URL` to a disposable evaluation-test database.
