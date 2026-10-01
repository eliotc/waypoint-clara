# CP-022 — Evaluation records need immutable history and link checks

Recorded on: 2026-09-27. Provenance: contemporaneous implementation and local database proof. Author: Codex (implementer and self-reviewer). Predecessor: CP-021 *(withheld)*. Layer: reusable evaluation harness.

## Before

The owner wanted evaluation outcomes that support later reference, repair planning and error trends. The existing four-record JSON schema supplied provenance and distinct assessments, but database import and trend queries were not yet established. A hybrid PostgreSQL projection was proposed.

## Evidence and limitations

The dangling `verification_assessment_id` in `event-clara-verified-001` and `issue-clara-001` was corrected with an explicit `assessment-` prefix, allowing complete bundle validation. The storage topology was refined per owner direction to a same-database, separate-schema architecture (`waypoint` database under `SCHEMA evaluation`) with three segregated group roles (`waypoint_eval_record_writer`, `waypoint_eval_record_reader`, `waypoint_eval_public_reader`) and a sanitized `public_assessment_summaries` view.

All 5 runs, 6 assessments, 2 issues, 18 criterion results, and 3 verification events imported cleanly; re-import confirmed 0 duplicates. Integration tests in `test_postgres_records.py` verified that writer update/delete is denied, write access to public course tables is denied, detailed readers access JSONB payloads, and public readers are strictly limited to sanitized denominator summaries. The local proof receipt at `evaluation/runs/local-eval-records-proof.json` was updated to reflect the verified role permissions and migration SHA (47adbefd...).

## Changed thinking

Schema validation alone does not guarantee cross-record integrity. Import should check links and denominators before a transaction. Current trend queries must omit superseded assessments while retaining them for audit; `evaluation.current_assessments` provides that projection. An issue's status is a snapshot; later disposition changes should be represented by verification events.

## Dispositions

Owner direction: build a generic, retrievable evaluation outcome structure and proceed with the PostgreSQL storage task. Implementation choice: separate database, append-only import role, JSONB payloads with promoted query columns, no runtime writer or public API in this slice. No release or broader schema policy acceptance is inferred from the local proof. The invalid source event remains open for reviewed correction. The existing filesystem writer can overwrite a same-ID JSON file, so it also needs an immutability guard before routine operational use.

## Next and revisit trigger

Review the migration/importer and correct the dangling source link with its provenance preserved. Then decide which records may be shown in an internal history API and how transcript evidence is retained. Revisit the current-assessment view if parallel adjudication branches become common; a simple unsuperseded-head view may then return more than one current assessment per run.
