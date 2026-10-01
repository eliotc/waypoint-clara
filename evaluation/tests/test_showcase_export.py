"""Tests for showcase_export validator, allowlist, referential integrity, and audio."""

import json
from pathlib import Path
import tempfile
import unittest
import wave

from evaluation.showcase_export import (
    validate_catalog,
    validate_example,
    convert_pcm_to_wav,
    ShowcaseValidationError,
)


def _create_tiny_wav(path: Path, sample_rate: int = 24000, channels: int = 1, num_frames: int = 240) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        # 16-bit silence
        wf.writeframes(b"\x00\x00" * num_frames * channels)


class TestShowcaseExport(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        self.scenario_dir = self.base / "test-scenario"
        self.scenario_dir.mkdir(parents=True)

        # Create tiny valid WAV
        self.audio_wav = self.scenario_dir / "turn-1.wav"
        _create_tiny_wav(self.audio_wav)

        self.valid_example = {
            "schema_version": "1.0",
            "id": "test-scenario",
            "title": "Test Scenario",
            "summary": "Testing showcase export",
            "student_goal": "Goal description",
            "model_id": "gemini-3.1-flash-live-preview",
            "captured_at_utc": "2026-09-17T12:00:00Z",
            "application_revision": "abcdef123456",
            "application_source_sha256": "1234567890abcdef",
            "environment_label": "Local read-only evaluation with fictional catalogue",
            "source_run_id": "run-test-1",
            "source_trace_sha256": "trace-sha-test-1",
            "input_kind": "scripted_text",
            "audio_kind": "captured_model_output",
            "criteria": [
                {"id": "crit-1", "description": "Accurately preserve experience."}
            ],
            "turns": [
                {
                    "id": "1",
                    "student_text": "I have three years of experience.",
                    "clara_text": "I see you have three years of IT experience.",
                    "audio_url": "turn-1.wav",
                    "duration_seconds": 0.01,
                }
            ],
            "evidence": [
                {
                    "id": "ev-1",
                    "tool_name": "search_courses",
                    "turn_id": "1",
                    "label": "Catalogue Entry",
                    "excerpt": "Entry requires 2 years experience.",
                }
            ],
            "findings": [
                {
                    "id": "find-1",
                    "criterion_id": "crit-1",
                    "disposition": "supported",
                    "explanation": "Clara correctly preserved experience.",
                    "turn_ids": ["1"],
                    "quote_references": ["three years of IT experience", "Entry requires 2 years experience."],
                    "evidence_ids": ["ev-1"],
                    "review_id": "rev-1",
                }
            ],
            "review": {
                "id": "rev-1",
                "author": "Hermes",
                "role": "implementer_self_review",
                "reviewed_at": "2026-09-17T12:30:00Z",
                "basis": "transcript_and_tool_evidence",
            },
            "judge": None,
            "limitations": [
                "Single run sample only."
            ],
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_valid_example_passes_cleanly(self):
        errors = validate_example(self.valid_example, base_dir=self.scenario_dir)
        self.assertEqual(errors, [])

    def test_unexpected_field_exclusion(self):
        data = dict(self.valid_example)
        data["unexpected_raw_tokens"] = "secret_dump"
        errors = validate_example(data, base_dir=self.scenario_dir)
        self.assertTrue(any("Disallowed top-level keys" in e for e in errors))

    def test_nested_turn_disallowed_field_rejected(self):
        data = json.loads(json.dumps(self.valid_example))
        data["turns"][0]["private_secret"] = "synthetic-sensitive-value"
        errors = validate_example(data, base_dir=self.scenario_dir)
        self.assertTrue(any("disallowed keys" in e and "private_secret" in e for e in errors))

    def test_missing_provenance_field_rejected(self):
        for req_field in ["captured_at_utc", "application_source_sha256", "source_trace_sha256", "application_revision"]:
            data = json.loads(json.dumps(self.valid_example))
            del data[req_field]
            errors = validate_example(data, base_dir=self.scenario_dir)
            self.assertTrue(any("Missing required keys" in e for e in errors))

            # Also test empty string provenance
            data2 = json.loads(json.dumps(self.valid_example))
            data2[req_field] = "   "
            errors2 = validate_example(data2, base_dir=self.scenario_dir)
            self.assertTrue(any("must be non-empty string" in e for e in errors2))

    def test_audio_sibling_prefix_path_traversal_rejected(self):
        data = json.loads(json.dumps(self.valid_example))
        data["turns"][0]["audio_url"] = "../sibling-dir/audio.wav"
        errors = validate_example(data, base_dir=self.scenario_dir)
        self.assertTrue(any("relative non-traversing" in e or "escapes base_dir" in e for e in errors))

    def test_publication_gate(self):
        from evaluation.showcase_export import validate_publication_readiness
        # Provisional self-review must fail publication gate
        data = json.loads(json.dumps(self.valid_example))
        errs = validate_publication_readiness(data)
        self.assertTrue(any("requires independent reviewer approval" in e for e in errs))

        # Approved reviewer passes gate
        data["review"]["role"] = "independent_reviewer"
        errs2 = validate_publication_readiness(data)
        self.assertEqual(errs2, [])

    def test_unsafe_paths_and_traversal_rejected(self):
        data = dict(self.valid_example)
        data["turns"] = [
            {
                "id": "1",
                "student_text": "Hello",
                "clara_text": "Hi",
                "audio_url": "../../../etc/passwd.wav",
            }
        ]
        errors = validate_example(data, base_dir=self.scenario_dir)
        self.assertTrue(any("audio_url must be relative non-traversing" in e or "traversal" in e for e in errors))

    def test_private_data_leak_rejected(self):
        data = dict(self.valid_example)
        data["summary"] = "Run log from /home/example-user/workspace/secret"
        errors = validate_example(data, base_dir=self.scenario_dir)
        self.assertTrue(any("Potential private data or path leak" in e for e in errors))

    def test_missing_audio_file_rejected(self):
        data = dict(self.valid_example)
        data["turns"] = [
            {
                "id": "1",
                "student_text": "Hello",
                "clara_text": "Hi",
                "audio_url": "nonexistent.wav",
            }
        ]
        errors = validate_example(data, base_dir=self.scenario_dir)
        self.assertTrue(any("audio file not found on disk" in e for e in errors))

    def test_corrupt_or_wrong_format_audio_rejected(self):
        # Create non-wav file
        bad_audio = self.scenario_dir / "bad.wav"
        bad_audio.write_bytes(b"not a wav file content")
        data = dict(self.valid_example)
        data["turns"] = [
            {
                "id": "1",
                "student_text": "Hello",
                "clara_text": "Hi",
                "audio_url": "bad.wav",
            }
        ]
        errors = validate_example(data, base_dir=self.scenario_dir)
        self.assertTrue(any("not valid WAV" in e for e in errors))

    def test_wrong_sample_rate_audio_rejected(self):
        # Create 44100Hz audio
        wrong_rate = self.scenario_dir / "wrong_rate.wav"
        _create_tiny_wav(wrong_rate, sample_rate=44100)
        data = dict(self.valid_example)
        data["turns"] = [
            {
                "id": "1",
                "student_text": "Hello",
                "clara_text": "Hi",
                "audio_url": "wrong_rate.wav",
            }
        ]
        errors = validate_example(data, base_dir=self.scenario_dir)
        self.assertTrue(any("must be 24000 Hz" in e for e in errors))

    def test_wrong_model_metadata_rejected(self):
        data = dict(self.valid_example)
        data["model_id"] = "gpt-4o"
        errors = validate_example(data, base_dir=self.scenario_dir)
        self.assertTrue(any("Unsupported model_id" in e for e in errors))

    def test_broken_referential_integrity_rejected(self):
        data = dict(self.valid_example)
        data["findings"] = [
            {
                "id": "find-1",
                "criterion_id": "nonexistent-criterion",
                "disposition": "supported",
                "explanation": "Test",
                "turn_ids": ["99"],
                "quote_references": [],
                "evidence_ids": ["ev-99"],
                "review_id": "rev-1",
            }
        ]
        errors = validate_example(data, base_dir=self.scenario_dir)
        self.assertTrue(any("references non-existent criterion_id" in e for e in errors))
        self.assertTrue(any("references non-existent turn_id" in e for e in errors))
        self.assertTrue(any("references non-existent evidence_id" in e for e in errors))

    def test_fabricated_quote_rejected(self):
        data = dict(self.valid_example)
        data["findings"] = [
            {
                "id": "find-1",
                "criterion_id": "crit-1",
                "disposition": "supported",
                "explanation": "Test",
                "turn_ids": ["1"],
                "quote_references": ["A fabricated quote that Clara never spoke"],
                "evidence_ids": ["ev-1"],
                "review_id": "rev-1",
            }
        ]
        errors = validate_example(data, base_dir=self.scenario_dir)
        self.assertTrue(any("does not match any referenced turn or evidence text verbatim" in e for e in errors))

    def test_catalog_validation(self):
        valid_cat = {
            "schema_version": "1.0",
            "entries": [
                {
                    "id": "test-scenario",
                    "title": "Test Title",
                    "summary": "Test Summary",
                    "status": "available",
                    "example_path": "test-scenario/example.json",
                },
                {
                    "id": "milestone-b-scenario",
                    "title": "Coming Soon",
                    "summary": "Review pending",
                    "status": "review_pending",
                    "example_path": None,
                },
            ],
        }
        # Fake example.json for catalog test
        ex_path = self.scenario_dir / "example.json"
        ex_path.write_text("{}", encoding="utf-8")

        errors = validate_catalog(valid_cat, base_dir=self.base)
        self.assertEqual(errors, [])

        # Test disallowed key in catalog
        bad_cat = dict(valid_cat)
        bad_cat["invalid_key"] = True
        errs = validate_catalog(bad_cat, base_dir=self.base)
        self.assertTrue(any("Disallowed top-level keys" in e for e in errs))

    def test_catalog_publication_gate_regression(self):
        # 1. With self-review example, gate check on catalog fails
        cat_file = Path("frontend/assets/showcase/catalog.json")
        if cat_file.is_file():
            with open(cat_file, "r", encoding="utf-8") as f:
                cat_data = json.load(f)
            errs = validate_catalog(cat_data, base_dir=cat_file.parent, check_gate=True)
            self.assertTrue(any("publication gate error" in e for e in errs))

            # Without gate check, it passes
            errs_no_gate = validate_catalog(cat_data, base_dir=cat_file.parent, check_gate=False)
            self.assertEqual(errs_no_gate, [])

    def test_delivered_example_regeneration_and_negative_controls(self):
        from evaluation.showcase_export import export_showcase_recording, verify_evidence_against_trace
        run_dir = Path("evaluation/runs/20260917T121741575855Z-20a985af")
        ex_file = Path("frontend/assets/showcase/returning-to-study/example.json")
        if not run_dir.is_dir() or not ex_file.is_file():
            return

        with open(ex_file, "r", encoding="utf-8") as f:
            delivered = json.load(f)

        # 1. Actual regeneration succeeds
        out_temp = Path(tempfile.mkdtemp())
        try:
            regen = export_showcase_recording(run_dir, "returning-to-study", out_temp, delivered)
            self.assertEqual(regen["id"], "returning-to-study")
            self.assertEqual(len(regen["turns"]), 2)
            self.assertEqual(len(regen["evidence"]), 3)
        finally:
            import shutil
            shutil.rmtree(out_temp, ignore_errors=True)

        # Load trace turns for unit-level evidence negative controls
        with open(run_dir / "trace-1-1.json", "r", encoding="utf-8") as f:
            trace_data = json.load(f)
        trace_turns = trace_data["turns"]

        # 2. Negative control: wrong tool
        bad_tool_ev = [
            {
                "id": "ev-wrong",
                "tool_name": "wrong_tool_name",
                "turn_id": "1",
                "label": "Test",
                "excerpt": "Bachelor degree in IT/quantitative field, or 2+ years of professional IT experience",
            }
        ]
        errs_tool = verify_evidence_against_trace(bad_tool_ev, trace_turns)
        self.assertTrue(any("no tool named 'wrong_tool_name' was called" in e for e in errs_tool))

        # 3. Negative control: argument-only evidence (present in args, not in result)
        # In turn 1, search_courses args is null or empty, but let's test a synthetic turn with args
        synthetic_turns = [
            {
                "tools": [
                    {
                        "name": "search_courses",
                        "args": {"query": "only in args not result"},
                        "result": {"courses": []},
                    }
                ]
            }
        ]
        arg_only_ev = [
            {
                "id": "ev-arg",
                "tool_name": "search_courses",
                "turn_id": "1",
                "label": "Arg test",
                "excerpt": "only in args not result",
            }
        ]
        errs_arg = verify_evidence_against_trace(arg_only_ev, synthetic_turns)
        self.assertTrue(any("appears only in tool arguments" in e for e in errs_arg))

        # 4. Negative control: ungrounded/invented excerpt
        ungrounded_ev = [
            {
                "id": "ev-fake",
                "tool_name": "search_courses",
                "turn_id": "1",
                "label": "Ungrounded test",
                "excerpt": "Bachelor degree in any field, OR at least 2 years of documented relevant work experience",
            }
        ]
        errs_ungrounded = verify_evidence_against_trace(ungrounded_ev, trace_turns)
        self.assertTrue(any("does not match recorded tool result" in e for e in errs_ungrounded))

        # 5. Negative control: partial structured excerpt with unsupported unparsed text
        partial_ev = [
            {
                "id": "ev-partial",
                "tool_name": "search_courses",
                "turn_id": "1",
                "label": "Partial test",
                "excerpt": "effective_has_bachelor_degree: false, guaranteed admission",
            }
        ]
        errs_partial = verify_evidence_against_trace(partial_ev, trace_turns)
        self.assertTrue(any("does not match recorded tool result" in e for e in errs_partial))

        # 6. Negative control: nonexistent field_path must not fall back to other fields
        bad_fp_ev = [
            {
                "id": "ev-bad-fp",
                "tool_name": "search_courses",
                "turn_id": "1",
                "field_path": "nonexistent_field",
                "label": "Bad field path",
                "excerpt": "false",
            }
        ]
        errs_fp = verify_evidence_against_trace(bad_fp_ev, trace_turns)
        self.assertTrue(any("does not exist in recorded tool result" in e for e in errs_fp))


if __name__ == "__main__":
    unittest.main()
