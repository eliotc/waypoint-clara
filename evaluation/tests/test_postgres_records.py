"""Offline checks for the PostgreSQL record importer; no database or model calls."""
import json
import tempfile
import unittest
from pathlib import Path

from evaluation.postgres_records import _ordered_assessments, load_bundle

ROOT = Path(__file__).resolve().parents[2]
# Labelled synthetic fixtures; operational evaluation records are not published.
RECORDS = ROOT / "evaluation" / "tests" / "fixtures" / "records"
FILES = {
    "runs": ["run-synthetic-scoped-negative.json"],
    "assessments": ["assessment-synthetic-scope-provisional.json", "assessment-synthetic-scope-adjudicated.json"],
    "issues": ["issue-synthetic-scoped-negative.json"],
    "verifications": ["event-synthetic-scope-adjudication.json"],
}


def copy_bundle(destination: Path) -> None:
    for folder, names in FILES.items():
        (destination / folder).mkdir()
        for name in names:
            (destination / folder / name).write_bytes((RECORDS / folder / name).read_bytes())


class TestPostgresRecords(unittest.TestCase):
    def test_original_and_regrade_are_distinct_and_ordered(self):
        with tempfile.TemporaryDirectory() as directory:
            copy_bundle(Path(directory))
            bundle = load_bundle(Path(directory))
        assessments = _ordered_assessments(bundle["assessments"])
        self.assertEqual([a["assessment_id"] for a in assessments], [
            "assessment-synthetic-scope-provisional", "assessment-synthetic-scope-adjudicated"])
        self.assertEqual(assessments[0]["results"][0]["outcome"], "issue_observed")
        self.assertEqual(assessments[1]["results"][0]["outcome"], "pass")

    def test_dangling_assessment_reference_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            copy_bundle(base)
            path = base / "verifications" / "event-synthetic-scope-adjudication.json"
            data = json.loads(path.read_text())
            data["verification_assessment_id"] = "missing-assessment"
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "missing assessment"):
                load_bundle(base)

    def test_denominators_must_equal_result_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            copy_bundle(base)
            path = base / "assessments" / "assessment-synthetic-scope-provisional.json"
            data = json.loads(path.read_text())
            data["denominators"]["passes"] = 1
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "denominators"):
                load_bundle(base)

    def test_empty_directory_is_not_a_successful_import(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "No run records"):
                load_bundle(Path(directory))

    def test_full_fixture_bundle_loads_and_validates_successfully(self):
        bundle = load_bundle(RECORDS)
        self.assertEqual(len(bundle["runs"]), 3)
        self.assertEqual(len(bundle["assessments"]), 4)
        self.assertEqual(len(bundle["issues"]), 2)
        self.assertEqual(len(bundle["verifications"]), 1)

    def test_role_privilege_boundaries(self):
        """Verify role privileges on a dedicated evaluation-test database (opt-in).

        Never reads .env or the application DATABASE_URL. To run, set
        RUN_EVAL_DB_ROLE_TESTS=1 and EVAL_ROLE_TEST_DATABASE_URL to a disposable
        evaluation-test database.
        """
        import os
        if os.environ.get("RUN_EVAL_DB_ROLE_TESTS") != "1":
            self.skipTest("Database role checks are opt-in (set RUN_EVAL_DB_ROLE_TESTS=1)")
        dsn = os.environ.get("EVAL_ROLE_TEST_DATABASE_URL")
        if not dsn:
            self.skipTest("EVAL_ROLE_TEST_DATABASE_URL must name a dedicated evaluation-test database")
        if dsn == os.environ.get("DATABASE_URL"):
            self.fail("EVAL_ROLE_TEST_DATABASE_URL must not be the application DATABASE_URL")
        import psycopg2
        try:
            conn = psycopg2.connect(dsn)
        except Exception as e:
            self.fail(f"Opted-in evaluation-test database is unreachable: {e}")
        with conn.cursor() as cur:
            # Check schema exists
            cur.execute("SELECT 1 FROM information_schema.schemata WHERE schema_name = 'evaluation';")
            if not cur.fetchone():
                self.skipTest("Evaluation schema not yet provisioned on this database")
                return

            # 1. Writer: SELECT and INSERT on eval tables, strictly NO UPDATE or DELETE
            cur.execute("""SELECT has_table_privilege('waypoint_eval_record_writer', 'evaluation.eval_runs', 'SELECT'),
                                  has_table_privilege('waypoint_eval_record_writer', 'evaluation.eval_runs', 'INSERT'),
                                  has_table_privilege('waypoint_eval_record_writer', 'evaluation.eval_runs', 'UPDATE'),
                                  has_table_privilege('waypoint_eval_record_writer', 'evaluation.eval_runs', 'DELETE');""")
            res1 = cur.fetchone()
            assert res1 is not None
            s, i, u, d = res1
            self.assertTrue(s)
            self.assertTrue(i)
            self.assertFalse(u)
            self.assertFalse(d)

            # 2. Detailed Reader: SELECT on eval tables, NO write grants
            cur.execute("""SELECT has_table_privilege('waypoint_eval_record_reader', 'evaluation.eval_runs', 'SELECT'),
                                  has_table_privilege('waypoint_eval_record_reader', 'evaluation.eval_runs', 'INSERT'),
                                  has_table_privilege('waypoint_eval_record_reader', 'evaluation.current_assessments', 'SELECT');""")
            res2 = cur.fetchone()
            assert res2 is not None
            s, i, v_s = res2
            self.assertTrue(s)
            self.assertFalse(i)
            self.assertTrue(v_s)

            # 3. Public Reader: SELECT on public_assessment_summaries ONLY, NO access to raw tables or current_assessments
            cur.execute("""SELECT has_table_privilege('waypoint_eval_public_reader', 'evaluation.public_assessment_summaries', 'SELECT'),
                                  has_table_privilege('waypoint_eval_public_reader', 'evaluation.eval_runs', 'SELECT'),
                                  has_table_privilege('waypoint_eval_public_reader', 'evaluation.current_assessments', 'SELECT');""")
            res3 = cur.fetchone()
            assert res3 is not None
            pub_s, raw_s, det_s = res3
            self.assertTrue(pub_s)
            self.assertFalse(raw_s)
            self.assertFalse(det_s)

            # 4. Writer cannot write to application tables if courses table exists
            cur.execute("SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'courses';")
            if cur.fetchone():
                cur.execute("""SELECT has_table_privilege('waypoint_eval_record_writer', 'public.courses', 'INSERT'),
                                      has_table_privilege('waypoint_eval_record_writer', 'public.courses', 'UPDATE'),
                                      has_table_privilege('waypoint_eval_record_writer', 'public.courses', 'DELETE');""")
                res4 = cur.fetchone()
                assert res4 is not None
                i, u, d = res4
                self.assertFalse(i)
                self.assertFalse(u)
                self.assertFalse(d)
        conn.close()
