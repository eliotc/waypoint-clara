"""Import validated evaluation records into the separate, append-only PostgreSQL store.

This is an offline importer. It never imports the application or reads DATABASE_URL.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from evaluation.contracts import validate

KINDS = {
    "runs": ("run", "run_record", "run_id"),
    "assessments": ("assessment", "assessment_record", "assessment_id"),
    "issues": ("issue", "issue_record", "issue_id"),
    "verifications": ("verification_event", "verification_record", "event_id"),
}


def load_bundle(base_dir: Path) -> dict[str, dict[str, dict[str, Any]]]:
    """Validate every record before any database write."""
    bundle: dict[str, dict[str, dict[str, Any]]] = {}
    for folder, (record_type, schema_kind, id_field) in KINDS.items():
        records: dict[str, dict[str, Any]] = {}
        for path in sorted((base_dir / folder).glob("*.json")):
            record = json.loads(path.read_text())
            validate(record, schema_kind)
            if record["record_type"] != record_type:
                raise ValueError(f"Unexpected record type in {path.name}")
            record_id = record[id_field]
            if record_id in records:
                raise ValueError(f"Duplicate {id_field}: {record_id}")
            records[record_id] = record
        bundle[folder] = records
    if not bundle["runs"]:
        raise ValueError("No run records found; check the records directory")
    _validate_links(bundle)
    return bundle


def _validate_links(bundle: dict[str, dict[str, dict[str, Any]]]) -> None:
    runs, assessments, issues, events = (
        bundle[k] for k in ("runs", "assessments", "issues", "verifications")
    )
    for record in assessments.values():
        if record["run_id"] not in runs:
            raise ValueError("Assessment refers to a missing run")
        prior = record.get("supersedes_assessment_id")
        if prior and (prior not in assessments or assessments[prior]["run_id"] != record["run_id"]):
            raise ValueError("Superseded assessment must exist for the same run")
        results = record["results"]
        if len({r["result_id"] for r in results}) != len(results):
            raise ValueError("Duplicate result ID within assessment")
        counts = {
            "passes": sum(r["outcome"] == "pass" for r in results),
            "issues": sum(r["outcome"] == "issue_observed" for r in results),
            "incomplete": sum(r["outcome"] == "unable_to_assess" for r in results),
            "execution_errors": sum(r["outcome"] == "execution_error" for r in results),
        }
        den = record["denominators"]
        if den["total_opportunities"] != len(results) or any(den[k] != v for k, v in counts.items()):
            raise ValueError("Assessment denominators do not match its results")
        for result in results:
            if result.get("issue_id") and result["issue_id"] not in issues:
                raise ValueError("Result refers to a missing issue")
    for record in issues.values():
        run_id = record.get("first_observed_in_run_id")
        assessment_id = record.get("first_observed_in_assessment_id")
        if run_id and run_id not in runs:
            raise ValueError("Issue refers to a missing run")
        if assessment_id and assessment_id not in assessments:
            raise ValueError("Issue refers to a missing assessment")
        if run_id and assessment_id and assessments[assessment_id]["run_id"] != run_id:
            raise ValueError("Issue first-observed run and assessment disagree")
        if any(value not in runs for value in record.get("linked_runs", [])):
            raise ValueError("Issue links to a missing run")
        if any(value not in assessments for value in record.get("linked_assessments", [])):
            raise ValueError("Issue links to a missing assessment")
    for record in events.values():
        if record.get("target_issue_id") and record["target_issue_id"] not in issues:
            raise ValueError("Verification refers to a missing issue")
        if record.get("verification_run_id") and record["verification_run_id"] not in runs:
            raise ValueError("Verification refers to a missing run")
        if record.get("verification_assessment_id") and record["verification_assessment_id"] not in assessments:
            raise ValueError("Verification refers to a missing assessment")
        if (record.get("verification_run_id") and record.get("verification_assessment_id")
                and assessments[record["verification_assessment_id"]]["run_id"] != record["verification_run_id"]):
            raise ValueError("Verification run and assessment disagree")
        if any(i not in assessments for i in record.get("superseded_assessment_ids", [])):
            raise ValueError("Verification refers to a missing superseded assessment")


def _ordered_assessments(records: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    pending = dict(records)
    ordered: list[dict[str, Any]] = []
    completed: set[str] = set()
    while pending:
        ready = [key for key, value in pending.items()
                 if not value.get("supersedes_assessment_id") or value["supersedes_assessment_id"] in completed]
        if not ready:
            raise ValueError("Assessment supersession cycle")
        for key in sorted(ready):
            ordered.append(pending.pop(key))
            completed.add(key)
    return ordered


def _insert_immutable(cursor: Any, table: str, key_columns: tuple[str, ...], values: tuple[Any, ...],
                      columns: tuple[str, ...], payload: dict[str, Any]) -> bool:
    """Insert once; reruns may be identical, but changed IDs must never replace evidence."""
    from psycopg2.extras import Json

    fields = ", ".join(columns)
    placeholders = ", ".join(["%s"] * len(columns))
    cursor.execute(
        f"INSERT INTO evaluation.{table} ({fields}) VALUES ({placeholders}) ON CONFLICT DO NOTHING",
        tuple(Json(v) if col == "payload" else v for col, v in zip(columns, values)),
    )
    inserted = bool(cursor.rowcount)
    where = " AND ".join(f"{column} = %s" for column in key_columns)
    cursor.execute(f"SELECT payload FROM evaluation.{table} WHERE {where}", values[:len(key_columns)])
    row = cursor.fetchone()
    if row is None or row[0] != payload:
        raise ValueError(f"Immutable record collision in {table}; use a new ID for a regrade")
    return inserted


def import_bundle(connection: Any, bundle: dict[str, dict[str, dict[str, Any]]]) -> dict[str, int]:
    """Import an entire validated bundle atomically. The caller owns commit/rollback."""
    inserted = {name: 0 for name in ("runs", "assessments", "issues", "results", "verifications")}
    with connection.cursor() as cursor:
        for r in bundle["runs"].values():
            env, target, scenario = r["environment"], r["target"], r["scenario"]
            inserted["runs"] += _insert_immutable(cursor, "eval_runs", ("run_id",),
                (r["run_id"], r["started_at"], r["status"], target["agent_name"], target["model_id"],
                 scenario.get("scenario_id"), env.get("git_commit"), env.get("git_dirty"),
                 env.get("dataset_version"), r),
                ("run_id", "started_at", "status", "agent_name", "model_id", "scenario_id",
                 "git_commit", "git_dirty", "dataset_version", "payload"), r)
        for a in _ordered_assessments(bundle["assessments"]):
            ev, den = a["evaluator"], a["denominators"]
            inserted["assessments"] += _insert_immutable(cursor, "eval_assessments", ("assessment_id",),
                (a["assessment_id"], a["run_id"], a["assessed_at"], ev["kind"], ev["reviewer_role"],
                 ev.get("model_id"), ev["rubric_version"], a.get("supersedes_assessment_id"),
                 den["total_opportunities"], den["passes"], den["issues"], den["incomplete"],
                 den["execution_errors"], a),
                ("assessment_id", "run_id", "assessed_at", "evaluator_kind", "reviewer_role",
                 "evaluator_model_id", "rubric_version", "supersedes_assessment_id", "total_opportunities",
                 "passes", "issues", "incomplete", "execution_errors", "payload"), a)
        for i in bundle["issues"].values():
            inserted["issues"] += _insert_immutable(cursor, "eval_issues", ("issue_id",),
                (i["issue_id"], i["title"], i["status"], i["primary_layer"],
                 i.get("first_observed_in_run_id"), i.get("first_observed_in_assessment_id"), i),
                ("issue_id", "title", "status", "primary_layer", "first_observed_run_id",
                 "first_observed_assessment_id", "payload"), i)
        for a in bundle["assessments"].values():
            for r in a["results"]:
                inserted["results"] += _insert_immutable(cursor, "eval_results", ("assessment_id", "result_id"),
                    (a["assessment_id"], r["result_id"], r["criterion_id"], r["outcome"],
                     r.get("severity"), r.get("tags", []), r.get("issue_id"), r),
                    ("assessment_id", "result_id", "criterion_id", "outcome", "severity", "tags",
                     "issue_id", "payload"), r)
        for e in bundle["verifications"].values():
            inserted["verifications"] += _insert_immutable(cursor, "eval_verification_events", ("event_id",),
                (e["event_id"], e["event_type"], e["timestamp"], e.get("target_issue_id"),
                 e.get("verification_run_id"), e.get("verification_assessment_id"), e),
                ("event_id", "event_type", "occurred_at", "target_issue_id", "verification_run_id",
                 "verification_assessment_id", "payload"), e)
    return inserted



def check_connection_scope(connection: Any) -> None:
    """Require a restricted identity with insert-only permissions on evaluation and no write grants on application tables."""
    with connection.cursor() as cursor:
        cursor.execute("""SELECT r.rolsuper, r.rolcreatedb, r.rolcreaterole
                          FROM pg_roles r WHERE r.rolname = current_user""")
        if any(cursor.fetchone()):
            raise ValueError("Evaluation import requires a restricted database login")

        # Must have INSERT and SELECT on evaluation tables
        cursor.execute("""SELECT has_table_privilege(current_user, 'evaluation.eval_runs', 'INSERT'),
                                 has_table_privilege(current_user, 'evaluation.eval_runs', 'SELECT')""")
        can_insert, can_select = cursor.fetchone()
        if not (can_insert and can_select):
            raise ValueError("Evaluation import login must have INSERT and SELECT on evaluation.eval_runs")

        # Must NOT have UPDATE or DELETE on evaluation tables
        cursor.execute("""SELECT has_table_privilege(current_user, 'evaluation.eval_runs', 'UPDATE'),
                                 has_table_privilege(current_user, 'evaluation.eval_runs', 'DELETE')""")
        if any(cursor.fetchone()):
            raise ValueError("Evaluation import login must not have UPDATE or DELETE grants on evaluation.eval_runs")

        # If application tables exist in public, writer must NOT have write access
        cursor.execute("""SELECT t.table_name
                          FROM information_schema.tables t
                          WHERE t.table_schema = 'public'
                            AND t.table_name IN ('courses', 'events', 'scholarships', 'knowledge_docs')
                            AND (
                                has_table_privilege(current_user, 'public.' || quote_ident(t.table_name), 'INSERT') OR
                                has_table_privilege(current_user, 'public.' || quote_ident(t.table_name), 'UPDATE') OR
                                has_table_privilege(current_user, 'public.' || quote_ident(t.table_name), 'DELETE')
                            )""")
        writeable = cursor.fetchall()
        if writeable:
            tables = [r[0] for r in writeable]
            raise ValueError(f"Evaluation import login must not have write access to application tables: {tables}")


def main() -> None:
    from dotenv import load_dotenv
    load_dotenv()
    parser = argparse.ArgumentParser(description="Import immutable evaluation records to a dedicated PostgreSQL database")
    parser.add_argument("records_dir", type=Path, help="Directory containing runs/, assessments/, issues/, verifications/")
    args = parser.parse_args()
    dsn = os.environ.get("EVAL_RECORDS_DATABASE_URL")
    if not dsn:
        parser.error("EVAL_RECORDS_DATABASE_URL is required; application DATABASE_URL is never used")
    bundle = load_bundle(args.records_dir)
    import psycopg2
    with psycopg2.connect(dsn) as connection:
        check_connection_scope(connection)
        result = import_bundle(connection, bundle)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
