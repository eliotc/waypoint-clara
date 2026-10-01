import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace

from evaluation.contracts import ROOT, read_asset, validate
from evaluation.graders import aggregate, exit_code, grade, pointer, typed_equal
from evaluation.isolation import configure_evaluation_database
from evaluation.legacy_checks import check, regression_exit_code
from evaluation.runner import digest, load_experiment, run_experiment

EXPERIMENT = ROOT / "evaluation/experiments/EXP-000/config.json"


class GraderTests(unittest.TestCase):
    def setUp(self):
        loaded = load_experiment(EXPERIMENT)
        self.scenario, self.persona = loaded["cases"][0]
        self.trace = loaded["adapter"].run(self.scenario, self.persona)

    def test_wrong_atar_fails_even_with_fluent_response(self):
        self.trace["turns"][0]["tools"][0]["arguments"]["student_atar"] = 85
        self.assertEqual(grade(self.trace, self.scenario["checks"])[0]["status"], "FAIL")

    def test_missing_tool_evidence_is_error_not_a_negative_assertion_pass(self):
        self.trace["turns"][0]["tools"] = []
        self.assertEqual(grade(self.trace, self.scenario["checks"])[0]["status"], "ERROR")

    def test_blank_turn_cannot_pass(self):
        self.trace["turns"][0]["assistant"] = " \n"
        rows = grade(self.trace, self.scenario["checks"])
        self.assertIn("FAIL", [r["status"] for r in rows])

    def test_semantics_require_review(self):
        self.assertEqual(grade(self.trace, self.scenario["checks"])[-1]["status"], "NEEDS_HUMAN")

    def test_nested_boolean_is_not_a_numeric_match(self):
        self.assertFalse(typed_equal({"count": True}, {"count": 1}))
        self.assertFalse(typed_equal([82.0], [82]))

    def test_unknown_status_never_becomes_success(self):
        self.assertEqual(exit_code(["PARTIAL"]), 2)
        self.assertEqual(aggregate(["UNKNOWN"]), "ERROR")

    def test_empty_and_incomplete_runs_have_nonzero_exit(self):
        for statuses in ([], ["ERROR"], ["SKIPPED"], ["PASS", "NEEDS_HUMAN"]):
            self.assertEqual(exit_code(statuses), 2)
        self.assertEqual(exit_code(["PASS"]), 0)
        self.assertEqual(exit_code(["PASS", "FAIL"]), 1)
        self.assertEqual(aggregate([]), "ERROR")

    def test_pointer_supports_escaped_keys_and_rejects_negative_indices(self):
        self.assertEqual(pointer({"a/b": {"~c": [82]}}, "/a~1b/~0c/0"), 82)
        with self.assertRaises(KeyError):
            pointer([82], "/-1")


class AssetTests(unittest.TestCase):
    def test_unknown_adapter_and_empty_scenarios_are_rejected(self):
        config = read_asset(EXPERIMENT, "experiment")
        for changes in ({"scenarios": []}, {"target": {**config["target"], "adapter": "live"}}):
            with self.assertRaises(ValueError):
                validate({**config, **changes}, "experiment")

    def test_unknown_fields_and_missing_grading_instruction_are_rejected(self):
        loaded = load_experiment(EXPERIMENT)
        scenario = copy.deepcopy(loaded["cases"][0][0])
        scenario["checks"][-1].pop("instruction")
        with self.assertRaises(ValueError):
            validate(scenario, "scenario")
        with self.assertRaises(ValueError):
            validate({**loaded["config"], "repetitons": 3}, "experiment")

    def test_trace_must_match_scenario_inputs(self):
        loaded = load_experiment(EXPERIMENT)
        scenario, persona = loaded["cases"][0]
        scenario["user_turns"] = ["A different student request"]
        with self.assertRaises(ValueError):
            loaded["adapter"].run(scenario, persona)

    def test_duplicate_scenario_ids_are_rejected(self):
        config = read_asset(EXPERIMENT, "experiment")
        config["dataset"] = str((EXPERIMENT.parent / config["dataset"]).resolve())
        config["contract"] = str((EXPERIMENT.parent / config["contract"]).resolve())
        config["target"]["fixture"] = str((EXPERIMENT.parent / config["target"]["fixture"]).resolve())
        scenario = str((EXPERIMENT.parent / config["scenarios"][0]).resolve())
        config["scenarios"] = [scenario, scenario]
        with tempfile.TemporaryDirectory(dir=ROOT / "evaluation") as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps(config))
            with self.assertRaisesRegex(ValueError, "Duplicate scenario"):
                load_experiment(path)

    def test_fixture_adapter_isolates_each_run(self):
        loaded = load_experiment(EXPERIMENT)
        scenario, persona = loaded["cases"][0]
        first = loaded["adapter"].run(scenario, persona)
        first["turns"][0]["tools"].clear()
        self.assertTrue(loaded["adapter"].run(scenario, persona)["turns"][0]["tools"])


class RunnerTests(unittest.TestCase):
    def test_runs_preserve_inputs_and_do_not_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            first, code = run_experiment(EXPERIMENT, Path(tmp))
            original = (first / "report.json").read_bytes()
            second, _ = run_experiment(EXPERIMENT, Path(tmp))
            self.assertNotEqual(first, second)
            self.assertEqual((first / "report.json").read_bytes(), original)
            self.assertEqual(code, 2)  # Known manual review, not a fixture failure.
            report = json.loads(original)
            self.assertEqual(report["summary"]["statuses"]["NEEDS_HUMAN"], 1)
            self.assertEqual(report["summary"]["statuses"]["PASS"], 1)
            manifest = json.loads((first / "manifest.json").read_text())
            self.assertIsNone(manifest["target"]["model"])
            self.assertEqual(manifest["evidence_kind"], "synthetic_fixture")
            for source in manifest["inputs"]:
                self.assertNotIn(".env", source["source"])
                self.assertEqual(digest((first / "inputs" / source["sha256"]).read_bytes()), source["sha256"])

    def test_adapter_fault_is_recorded_as_error(self):
        loaded = load_experiment(EXPERIMENT)
        with tempfile.TemporaryDirectory() as tmp, patch("evaluation.runner.load_experiment", return_value=loaded):
            with patch.object(loaded["adapter"], "run", side_effect=RuntimeError("synthetic failure")):
                folder, code = run_experiment(EXPERIMENT, Path(tmp))
            report = json.loads((folder / "report.json").read_text())
            self.assertEqual(code, 2)
            self.assertEqual(report["summary"]["statuses"]["ERROR"], 2)

    def test_cli_validate_and_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            for command, expected in ((["validate", str(EXPERIMENT)], 0),
                                      (["run", str(EXPERIMENT), "--out", tmp], 2)):
                result = subprocess.run([sys.executable, "-m", "evaluation", *command],
                                        cwd=ROOT, capture_output=True, text=True)
                self.assertEqual(result.returncode, expected, result.stderr)


class LegacyTests(unittest.TestCase):
    def test_empty_responses_never_pass(self):
        for sid in ("RG-01", "RG-03", "RG-04", "RG-06", "RG-08", "RT-PRIV-05"):
            self.assertEqual(check(sid, [{"text": "", "tools": []}])[0], "FAIL")
        self.assertEqual(check("RG-01", [])[0], "ERROR")

    def test_negation_and_employer_claims_are_reviewed(self):
        for text in ("I cannot guarantee a job at Google.", "We guarantee a job at Google.",
                     "Graduates work at Google Cloud partners."):
            self.assertEqual(check("RG-03", [{"text": text, "tools": []}])[0], "NEEDS_HUMAN")

    def test_fabricated_email_in_an_earlier_turn_is_detected(self):
        turns = [{"text": "Booking", "tools": ["book_campus_tour"], "book_email": "invented@example.com"},
                 {"text": "Choose another date", "tools": [], "book_email": None}]
        self.assertEqual(check("RG-08", turns)[0], "FAIL")

    def test_failed_tool_execution_and_exhausted_loop_are_errors(self):
        for error in ("ToolRoundLimitExceeded", "ConnectionError"):
            self.assertEqual(check("RG-06", [{"text": "", "tools": [], "error": error}])[0], "ERROR")

    def test_review_and_no_results_are_not_success(self):
        self.assertEqual(regression_exit_code([]), 2)
        self.assertEqual(regression_exit_code([{"outcome": "NEEDS_HUMAN"}]), 2)

    def test_module_import_does_not_require_credentials_or_load_sdk(self):
        script = ROOT / "testing/red-team/run_regression.py"
        code = ("import importlib.util, sys; "
                f"s=importlib.util.spec_from_file_location('regression', {str(script)!r}); "
                "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
                "assert 'google.genai' not in sys.modules; assert m.TOOL_FUNCS == {}")
        result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_actual_legacy_loop_retains_calls_on_exhaustion_or_model_error(self):
        spec = importlib.util.spec_from_file_location("regression_test", ROOT / "testing/red-team/run_regression.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.t = SimpleNamespace(
            GenerateContentConfig=lambda **kw: kw,
            Content=lambda **kw: kw,
            Part=SimpleNamespace(from_function_response=lambda **kw: kw),
        )
        module.TOOL_FUNCS = {"search_events": lambda **kw: {"count": 0}}
        content = SimpleNamespace(parts=[SimpleNamespace(function_call=SimpleNamespace(name="search_events", args={}))])
        response = SimpleNamespace(candidates=[SimpleNamespace(content=content)])
        generate = Mock(return_value=response)
        client = SimpleNamespace(models=SimpleNamespace(generate_content=generate))
        result = module.run_turn(client, "test-model", {}, [])
        self.assertEqual(result["error"], "ToolRoundLimitExceeded")
        self.assertEqual(len(result["calls"]), 6)
        generate.side_effect = [response, RuntimeError("model unavailable")]
        result = module.run_turn(client, "test-model", {}, [])
        self.assertEqual(result["error"], "RuntimeError")
        self.assertEqual(len(result["calls"]), 1)

    def test_legacy_empty_report_returns_false(self):
        import eval_suite
        with tempfile.TemporaryDirectory() as tmp, patch.object(eval_suite, "__file__", str(Path(tmp) / "eval_suite.py")):
            self.assertFalse(eval_suite.print_report([], [], []))

    def test_legacy_missing_requested_layer_is_reported(self):
        import eval_suite
        with tempfile.TemporaryDirectory() as tmp, patch.object(eval_suite, "__file__", str(Path(tmp) / "eval_suite.py")):
            self.assertFalse(eval_suite.print_report([{"passed": True}], [], [], ["layer1", "layer2"]))
            report = json.loads(next(Path(tmp).rglob("report.json")).read_text())
            self.assertEqual(report["coverage"]["missing"], ["layer2"])
            self.assertEqual(report["summary"]["status"], "INCOMPLETE")


class IsolationTests(unittest.TestCase):
    def test_no_implicit_database_access(self):
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://localhost/app"}, clear=True):
            with self.assertRaises(ValueError):
                configure_evaluation_database()
            self.assertEqual(os.environ["DATABASE_URL"], "postgresql://localhost/app")

    def test_same_database_with_different_credentials_is_rejected(self):
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://user@localhost/app",
                                   "EVAL_DATABASE_URL": "postgres://other@localhost:5432/app"}, clear=True):
            with self.assertRaises(ValueError):
                configure_evaluation_database()

    def test_explicit_disposable_database_is_selected(self):
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://localhost/app",
                                   "EVAL_DATABASE_URL": "postgresql://localhost/eval_test"}, clear=True):
            configure_evaluation_database()
            self.assertEqual(os.environ["DATABASE_URL"], "postgresql://localhost/eval_test")


if __name__ == "__main__":
    unittest.main()
