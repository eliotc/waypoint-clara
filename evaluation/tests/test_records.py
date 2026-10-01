"""Unit tests for Waypoint evaluation records, schema validation, and metrics calculation."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from evaluation.contracts import validate
from evaluation.records import calculate_metrics, compute_environment_hashes, save_record

ROOT = Path(__file__).resolve().parents[2]
# Labelled synthetic fixtures; operational evaluation records are not published.
RECORDS_DIR = ROOT / "evaluation" / "tests" / "fixtures" / "records"


class TestEvaluationRecords(unittest.TestCase):
    def test_example_records_validate_against_schema(self):
        """All mapped example files must be strictly valid under eval_records_v1.json."""
        runs_dir = RECORDS_DIR / "runs"
        assessments_dir = RECORDS_DIR / "assessments"
        issues_dir = RECORDS_DIR / "issues"
        verifications_dir = RECORDS_DIR / "verifications"

        for p in runs_dir.glob("*.json"):
            data = json.loads(p.read_text())
            validate(data, "run_record")

        for p in assessments_dir.glob("*.json"):
            data = json.loads(p.read_text())
            validate(data, "assessment_record")

        for p in issues_dir.glob("*.json"):
            data = json.loads(p.read_text())
            validate(data, "issue_record")

        for p in verifications_dir.glob("*.json"):
            data = json.loads(p.read_text())
            validate(data, "verification_record")

    def test_reconstruct_case_1_genuine_defect(self):
        """Reconstruct conditions, evaluator, and evidence for genuine Clara defect."""
        run = json.loads((RECORDS_DIR / "runs" / "run-synthetic-catalogue-contradiction.json").read_text())
        assessment = json.loads((RECORDS_DIR / "assessments" / "assessment-synthetic-catalogue-contradiction.json").read_text())

        # 1. Environment reconstruction
        self.assertEqual(run["target"]["model_id"], "example-live-model")
        self.assertTrue(run["environment"]["git_dirty"])
        self.assertTrue(len(run["environment"]["application_source_sha256"]) == 64)
        self.assertEqual(run["environment"]["dataset_version"], "clara-local-seed-v2")

        # 2. Evaluator reconstruction
        self.assertEqual(assessment["evaluator"]["kind"], "model")
        self.assertEqual(assessment["evaluator"]["reviewer_role"], "automated_judge")
        self.assertEqual(assessment["evaluator"]["rubric_version"], "example-judge-rubric-v1")

        # 3. Evidence reconstruction
        issue_res = next(r for r in assessment["results"] if r["criterion_id"] == "grounded_advice")
        self.assertEqual(issue_res["outcome"], "issue_observed")
        self.assertIn("catalog_contradiction", issue_res["tags"])
        
        # Check both cited excerpts exist
        turn_excerpt = next(e for e in issue_res["evidence_refs"] if e["location"].get("speaker") == "Clara")
        tool_excerpt = next(e for e in issue_res["evidence_refs"] if e["location"].get("speaker") == "tool")
        self.assertIn("Full-time, not Online", turn_excerpt["excerpt"])
        self.assertEqual("study_mode: Online", tool_excerpt["excerpt"])

    def test_reconstruct_case_2_evaluator_false_positive_and_adjudication(self):
        """Reconstruct a scoped-conclusion adjudication, superseding assessment, and disposition change."""
        issue = json.loads((RECORDS_DIR / "issues" / "issue-synthetic-scoped-negative.json").read_text())
        prov_assessment = json.loads((RECORDS_DIR / "assessments" / "assessment-synthetic-scope-provisional.json").read_text())
        event = json.loads((RECORDS_DIR / "verifications" / "event-synthetic-scope-adjudication.json").read_text())
        adj_assessment = json.loads((RECORDS_DIR / "assessments" / "assessment-synthetic-scope-adjudicated.json").read_text())

        # Provisional assessment failed
        self.assertEqual(prov_assessment["results"][0]["outcome"], "issue_observed")
        self.assertIsNone(prov_assessment["supersedes_assessment_id"])

        # Verification event records owner adjudication
        self.assertEqual(event["actor"], "example-owner")
        self.assertEqual(event["actor_role"], "owner")
        self.assertEqual(event["disposition_change"]["new_status"], "rejected_not_a_defect")
        self.assertIn("assessment-synthetic-scope-provisional", event["superseded_assessment_ids"])

        # Superseding assessment is immutable and explicitly points back to the superseded one
        self.assertEqual(adj_assessment["supersedes_assessment_id"], "assessment-synthetic-scope-provisional")
        self.assertEqual(adj_assessment["results"][0]["outcome"], "pass")
        self.assertEqual(adj_assessment["evaluator"]["reviewer_role"], "independent_review")

        # The issue record retains the hypothesis and status
        self.assertEqual(issue["status"], "rejected_not_a_defect")
        self.assertEqual(issue["primary_layer"], "domain_evaluation")

    def test_reconstruct_case_3_incomplete_assessment(self):
        """Verify incomplete assessments are captured in denominators without distorting pass/fail."""
        assessment = json.loads((RECORDS_DIR / "assessments" / "assessment-synthetic-incomplete.json").read_text())
        denoms = assessment["denominators"]
        self.assertEqual(denoms["total_opportunities"], 4)
        self.assertEqual(denoms["passes"], 3)
        self.assertEqual(denoms["issues"], 0)
        self.assertEqual(denoms["incomplete"], 1)

        inc_res = next(r for r in assessment["results"] if r["criterion_id"] == "grounded_advice")
        self.assertEqual(inc_res["outcome"], "unable_to_assess")
        self.assertIn("fail_closed_validation", inc_res["tags"])

    def test_metrics_calculation_and_denominators(self):
        """Compute metrics over assessments, verifying proper denominators and failure rates."""
        a1 = json.loads((RECORDS_DIR / "assessments" / "assessment-synthetic-catalogue-contradiction.json").read_text())
        a3 = json.loads((RECORDS_DIR / "assessments" / "assessment-synthetic-incomplete.json").read_text())

        metrics = calculate_metrics([a1, a3])
        # Total opportunities = 4 + 4 = 8
        self.assertEqual(metrics["total_opportunities"], 8)
        # Passes = 3 + 3 = 6
        self.assertEqual(metrics["passes"], 6)
        # Issues = 1 + 0 = 1
        self.assertEqual(metrics["issues"], 1)
        # Incomplete = 0 + 1 = 1
        self.assertEqual(metrics["incomplete"], 1)
        # Decided checks = 6 + 1 = 7. Failure rate of evaluated = 1 / 7 = 0.1429
        self.assertAlmostEqual(metrics["failure_rate_of_evaluated"], 1 / 7, places=4)
        # Coverage rate = 7 / 8 = 0.875
        self.assertEqual(metrics["coverage_rate"], 0.875)
        # Incomplete rate = 1 / 8 = 0.125
        self.assertEqual(metrics["incomplete_rate"], 0.125)

        # Issue breakdowns
        self.assertEqual(metrics["issues_by_criterion"]["grounded_advice"], 1)
        self.assertEqual(metrics["issues_by_tag"]["catalog_contradiction"], 1)

    def test_compute_environment_hashes(self):
        """compute_environment_hashes extracts real git info and source sha256."""
        env = compute_environment_hashes(ROOT)
        self.assertIn("git_commit", env)
        self.assertIn("git_dirty", env)
        self.assertEqual(len(env["application_source_sha256"]), 64)
        self.assertEqual(len(env["prompt_sha256"]), 64)
        self.assertEqual(env["dataset_version"], "clara-local-seed-v2")


    def test_record_showcase_run_integration(self):
        """record_showcase_run creates valid RunRecord and AssessmentRecord from a live trace."""
        import tempfile
        from evaluation.records import record_showcase_run

        mock_trace = {
            "run_id": "test-mock-run-123",
            "scenario": {
                "id": "returning-to-study",
                "version": "2.0.0",
                "name": "Returning to Study",
                "student_messages": ["hi", "question 2"],
            },
            "provenance": {"model_id": "gemini-3.8-live"},
            "status": "completed",
            "completed_turns": 2,
            "audio_bytes": 45000,
            "created_at": 1727180000.0,
            "findings": [
                {
                    "criterion_id": "grounded_advice",
                    "status": "issue_observed",
                    "summary": "A material unsupported claim was identified: Full-time not Online contradicts catalogue.",
                    "evidence": [{"id": "turn-1", "quote": "Full-time, not Online"}],
                },
                {
                    "criterion_id": "preserved_facts",
                    "status": "supported",
                    "summary": "Student experience preserved accurately.",
                    "evidence": [{"id": "turn-2", "quote": "1 year experience"}],
                }
            ]
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            run_p, assess_p = record_showcase_run(mock_trace, base_dir=Path(tmpdir))
            self.assertIsNotNone(run_p)
            self.assertIsNotNone(assess_p)
            assert run_p is not None and assess_p is not None
            self.assertTrue(run_p.is_file())
            self.assertTrue(assess_p.is_file())

            run_data = json.loads(run_p.read_text())
            validate(run_data, "run_record")
            self.assertEqual(run_data["run_id"], "test-mock-run-123")

            assess_data = json.loads(assess_p.read_text())
            validate(assess_data, "assessment_record")
            self.assertEqual(assess_data["denominators"]["total_opportunities"], 2)
            self.assertEqual(assess_data["denominators"]["issues"], 1)
            self.assertEqual(assess_data["denominators"]["passes"], 1)


    def test_save_record_immutability_guard(self):
        """save_record allows idempotent identical writes but rejects changed payloads under the same ID."""
        import tempfile
        from evaluation.records import save_record
        sample_path = RECORDS_DIR / "runs" / "run-synthetic-scoped-negative.json"
        sample_run = json.loads(sample_path.read_text())
        with tempfile.TemporaryDirectory() as td:
            base_dir = Path(td)
            p1 = save_record(sample_run, "run_record", base_dir=base_dir)
            self.assertTrue(p1.exists())
            # Idempotent write should succeed
            p2 = save_record(sample_run, "run_record", base_dir=base_dir)
            self.assertEqual(p1, p2)
            # Mutated payload under same ID must raise ValueError
            mutated = dict(sample_run)
            mutated["status"] = "failed"
            with self.assertRaisesRegex(ValueError, "Immutable record collision"):
                save_record(mutated, "run_record", base_dir=base_dir)

    def test_save_record_two_assessments_for_one_run(self):
        """save_record names assessments by assessment_id, allowing multiple assessments for the same run."""
        import tempfile
        from evaluation.records import save_record
        sample_path = RECORDS_DIR / "assessments" / "assessment-synthetic-scope-provisional.json"
        prov = json.loads(sample_path.read_text())
        adj_path = RECORDS_DIR / "assessments" / "assessment-synthetic-scope-adjudicated.json"
        adj = json.loads(adj_path.read_text())
        
        self.assertEqual(prov["run_id"], adj["run_id"])
        self.assertNotEqual(prov["assessment_id"], adj["assessment_id"])
        
        with tempfile.TemporaryDirectory() as td:
            base_dir = Path(td)
            p_prov = save_record(prov, "assessment_record", base_dir=base_dir)
            p_adj = save_record(adj, "assessment_record", base_dir=base_dir)
            self.assertEqual(p_prov.name, f"{prov['assessment_id']}.json")
            self.assertEqual(p_adj.name, f"{adj['assessment_id']}.json")
            self.assertTrue(p_prov.exists())
            self.assertTrue(p_adj.exists())

    def test_save_record_two_executions_for_one_scenario(self):
        """save_record names runs by run_id, allowing multiple executions of the same scenario."""
        import tempfile
        from evaluation.records import save_record
        sample_path = RECORDS_DIR / "runs" / "run-synthetic-catalogue-contradiction.json"
        run1 = json.loads(sample_path.read_text())
        run2 = dict(run1)
        run2["run_id"] = "run-synthetic-catalogue-contradiction-repeat"
        run2["started_at"] = "2026-09-27T12:00:00Z"
        
        with tempfile.TemporaryDirectory() as td:
            base_dir = Path(td)
            p1 = save_record(run1, "run_record", base_dir=base_dir)
            p2 = save_record(run2, "run_record", base_dir=base_dir)
            self.assertEqual(p1.name, f"{run1['run_id']}.json")
            self.assertEqual(p2.name, f"{run2['run_id']}.json")
            self.assertTrue(p1.exists())
            self.assertTrue(p2.exists())

if __name__ == "__main__":
    unittest.main()
