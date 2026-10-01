"""Offline exporter and validator for public showcase evaluation recordings.

Strict allowlist-only validation and export. Never exposes private paths,
internal session tokens, full database snapshots, or unverified claims.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any
import wave

# Top-level allowlists
EXAMPLE_ALLOWLIST = {
    "schema_version",
    "id",
    "title",
    "summary",
    "student_goal",
    "model_id",
    "captured_at_utc",
    "application_revision",
    "application_source_sha256",
    "environment_label",
    "source_run_id",
    "source_trace_sha256",
    "input_kind",
    "audio_kind",
    "criteria",
    "turns",
    "evidence",
    "findings",
    "review",
    "judge",
    "limitations",
}

REQUIRED_EXAMPLE_KEYS = {
    "schema_version",
    "id",
    "title",
    "summary",
    "student_goal",
    "model_id",
    "captured_at_utc",
    "application_revision",
    "application_source_sha256",
    "environment_label",
    "source_run_id",
    "source_trace_sha256",
    "input_kind",
    "audio_kind",
    "criteria",
    "turns",
    "evidence",
    "findings",
    "review",
    "limitations",
}

# Nested item allowlists
TURN_ALLOWLIST = {
    "id",
    "student_text",
    "clara_text",
    "audio_url",
    "duration_seconds",
}

CRITERION_ALLOWLIST = {
    "id",
    "description",
}

EVIDENCE_ALLOWLIST = {
    "id",
    "tool_name",
    "turn_id",
    "label",
    "excerpt",
    "field_path",
}

FINDING_ALLOWLIST = {
    "id",
    "criterion_id",
    "disposition",
    "explanation",
    "turn_ids",
    "quote_references",
    "evidence_ids",
    "review_id",
}

REVIEW_ALLOWLIST = {
    "id",
    "author",
    "role",
    "label",
    "reviewed_at",
    "basis",
}

JUDGE_ALLOWLIST = {
    "model_id",
    "evaluated_at",
    "verdict",
    "rubric_version",
}

CATALOG_ALLOWLIST = {
    "schema_version",
    "entries",
}

ENTRY_ALLOWLIST = {
    "id",
    "title",
    "summary",
    "status",
    "example_path",
}

SUPPORTED_MODEL_IDS = {
    "gemini-3.1-flash-live-preview",
}

PRIVATE_PATTERN = re.compile(
    r"(?:/home/|/Users/|[A-Za-z]:\\|postgres://|postgresql://|Bearer\s+|x-waypoint|\.env|evaluation/runs/)",
    re.IGNORECASE,
)


class ShowcaseValidationError(Exception):
    """Raised when a showcase artifact fails validation."""

    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


def validate_catalog(
    data: dict[str, Any],
    base_dir: Path | None = None,
    check_gate: bool = False,
) -> list[str]:
    """Validate catalog.json structure, allowlist, path containment, and publication readiness."""
    errors: list[str] = []

    extra = set(data.keys()) - CATALOG_ALLOWLIST
    if extra:
        errors.append(f"Disallowed top-level keys in catalog: {sorted(extra)}")

    if data.get("schema_version") != "1.0":
        errors.append(f"Expected schema_version '1.0', got {data.get('schema_version')!r}")

    entries = data.get("entries")
    if not isinstance(entries, list) or len(entries) == 0:
        errors.append("Catalog 'entries' must be a non-empty list")
        return errors

    seen_ids: set[str] = set()
    for idx, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append(f"Catalog entry [{idx}] must be a dict")
            continue

        entry_extra = set(entry.keys()) - ENTRY_ALLOWLIST
        if entry_extra:
            errors.append(f"Catalog entry [{idx}] has disallowed keys: {sorted(entry_extra)}")

        entry_id = entry.get("id")
        if not entry_id or not isinstance(entry_id, str):
            errors.append(f"Catalog entry [{idx}] missing string 'id'")
        elif entry_id in seen_ids:
            errors.append(f"Duplicate catalog entry id: {entry_id!r}")
        else:
            seen_ids.add(entry_id)

        if not entry.get("title") or not isinstance(entry.get("title"), str):
            errors.append(f"Catalog entry [{idx}] missing string 'title'")

        status = entry.get("status")
        if status not in {"available", "review_pending", "unavailable"}:
            errors.append(f"Catalog entry [{idx}] has invalid status: {status!r}")

        example_path = entry.get("example_path")
        if status == "available":
            if not example_path or not isinstance(example_path, str):
                errors.append(f"Available entry {entry_id!r} must have string 'example_path'")
            elif base_dir:
                resolved_base = base_dir.resolve()
                target = (base_dir / example_path).resolve()
                try:
                    if not target.is_relative_to(resolved_base):
                        errors.append(f"Catalog entry [{idx}] example_path escapes base_dir: {example_path!r}")
                    elif not target.is_file():
                        errors.append(f"Referenced example_path not found: {example_path!r}")
                    elif check_gate:
                        # Validate the referenced example file and apply the publication gate
                        with open(target, "r", encoding="utf-8") as f:
                            ex_data = json.load(f)
                        ex_errs = validate_example(ex_data, base_dir=target.parent)
                        for ee in ex_errs:
                            errors.append(f"Catalog entry {entry_id!r} example error: {ee}")
                        gate_errs = validate_publication_readiness(ex_data)
                        for ge in gate_errs:
                            errors.append(f"Catalog entry {entry_id!r} publication gate error: {ge}")
                except (ValueError, AttributeError) as err:
                    errors.append(f"Invalid path containment for example_path {example_path!r}: {err}")
        elif example_path is not None and not isinstance(example_path, str):
            errors.append(f"Entry {entry_id!r} example_path must be string or null")

    return errors


def validate_example(data: dict[str, Any], base_dir: Path | None = None) -> list[str]:
    """Validate example.json schema, nested allowlists, provenance, referential integrity, and audio."""
    errors: list[str] = []

    # 1. Allowlist check
    extra = set(data.keys()) - EXAMPLE_ALLOWLIST
    if extra:
        errors.append(f"Disallowed top-level keys in example: {sorted(extra)}")

    # 2. Required keys check
    missing = REQUIRED_EXAMPLE_KEYS - set(data.keys())
    if missing:
        errors.append(f"Missing required keys in example: {sorted(missing)}")

    # Validate required string provenance fields are non-empty
    for req_field in [
        "captured_at_utc",
        "application_revision",
        "application_source_sha256",
        "source_run_id",
        "source_trace_sha256",
    ]:
        val = data.get(req_field)
        if not val or not isinstance(val, str) or not val.strip():
            errors.append(f"Required provenance field {req_field!r} must be non-empty string")

    # 3. Schema version
    if data.get("schema_version") != "1.0":
        errors.append(f"Expected schema_version '1.0', got {data.get('schema_version')!r}")

    # 4. Model ID
    model_id = data.get("model_id")
    if model_id not in SUPPORTED_MODEL_IDS:
        errors.append(f"Unsupported model_id: {model_id!r}. Must be one of {sorted(SUPPORTED_MODEL_IDS)}")

    # 5. Privacy and path leaks in string values
    def check_leak(val: Any, loc: str):
        if isinstance(val, str):
            if ".." in val:
                errors.append(f"Path traversal '..' found in {loc}: {val!r}")
            if PRIVATE_PATTERN.search(val):
                errors.append(f"Potential private data or path leak in {loc}: {val!r}")
        elif isinstance(val, dict):
            for k, v in val.items():
                check_leak(v, f"{loc}.{k}")
        elif isinstance(val, list):
            for i, v in enumerate(val):
                check_leak(v, f"{loc}[{i}]")

    check_leak(data, "example")

    # 6. Criteria validation
    criteria = data.get("criteria", [])
    criteria_map: dict[str, str] = {}
    if not isinstance(criteria, list) or len(criteria) == 0:
        errors.append("Example must define at least one criterion")
    else:
        for idx, crit in enumerate(criteria):
            if not isinstance(crit, dict):
                errors.append(f"Criterion [{idx}] must be dict")
                continue
            crit_extra = set(crit.keys()) - CRITERION_ALLOWLIST
            if crit_extra:
                errors.append(f"Criterion [{idx}] has disallowed keys: {sorted(crit_extra)}")
            if "id" not in crit or "description" not in crit:
                errors.append(f"Criterion [{idx}] must have 'id' and 'description'")
                continue
            cid = crit["id"]
            if cid in criteria_map:
                errors.append(f"Duplicate criterion ID: {cid!r}")
            criteria_map[cid] = crit["description"]

    # 7. Turns and Audio validation (nested allowlist & containment)
    turns = data.get("turns", [])
    turn_map: dict[str, dict[str, Any]] = {}
    seen_audio_urls: set[str] = set()

    if not isinstance(turns, list) or len(turns) == 0:
        errors.append("Example must define at least one turn")
    else:
        for idx, turn in enumerate(turns):
            if not isinstance(turn, dict):
                errors.append(f"Turn [{idx}] must be dict")
                continue

            turn_extra = set(turn.keys()) - TURN_ALLOWLIST
            if turn_extra:
                errors.append(f"Turn [{idx}] has disallowed keys: {sorted(turn_extra)}")

            tid = str(turn.get("id"))
            if not tid:
                errors.append(f"Turn [{idx}] missing 'id'")
                continue
            if tid in turn_map:
                errors.append(f"Duplicate turn ID: {tid!r}")
            turn_map[tid] = turn

            # Audio file checks
            audio_url = turn.get("audio_url")
            if not audio_url or not isinstance(audio_url, str):
                errors.append(f"Turn {tid} missing string 'audio_url'")
            else:
                if audio_url in seen_audio_urls:
                    errors.append(f"Turn {tid} uses duplicate audio_url: {audio_url!r}")
                seen_audio_urls.add(audio_url)

                if os.path.isabs(audio_url) or audio_url.startswith("/") or ".." in audio_url:
                    errors.append(f"Turn {tid} audio_url must be relative non-traversing filename: {audio_url!r}")
                elif not audio_url.endswith(".wav"):
                    errors.append(f"Turn {tid} audio_url must end with .wav: {audio_url!r}")
                elif base_dir:
                    resolved_base = base_dir.resolve()
                    audio_path = (base_dir / audio_url).resolve()
                    try:
                        if not audio_path.is_relative_to(resolved_base):
                            errors.append(f"Turn {tid} audio path escapes base_dir: {audio_url!r}")
                        elif not audio_path.is_file():
                            errors.append(f"Turn {tid} audio file not found on disk: {audio_path}")
                        elif audio_path.stat().st_size == 0:
                            errors.append(f"Turn {tid} audio file is empty: {audio_path}")
                        else:
                            try:
                                with wave.open(str(audio_path), "rb") as wf:
                                    if wf.getnchannels() != 1:
                                        errors.append(f"Turn {tid} audio must be 1 channel (mono), got {wf.getnchannels()}")
                                    if wf.getframerate() != 24000:
                                        errors.append(f"Turn {tid} audio must be 24000 Hz, got {wf.getframerate()}")
                            except Exception as e:
                                errors.append(f"Turn {tid} audio file is not valid WAV: {e}")
                    except (ValueError, AttributeError):
                        errors.append(f"Turn {tid} audio path resolution error: {audio_url!r}")

    # 8. Evidence validation (nested allowlist)
    evidence_list = data.get("evidence", [])
    evidence_map: dict[str, dict[str, Any]] = {}
    if not isinstance(evidence_list, list):
        errors.append("'evidence' must be a list")
    else:
        for idx, ev in enumerate(evidence_list):
            if not isinstance(ev, dict):
                errors.append(f"Evidence [{idx}] must be dict")
                continue
            ev_extra = set(ev.keys()) - EVIDENCE_ALLOWLIST
            if ev_extra:
                errors.append(f"Evidence [{idx}] has disallowed keys: {sorted(ev_extra)}")

            ev_id = ev.get("id")
            if not ev_id or not isinstance(ev_id, str):
                errors.append(f"Evidence [{idx}] missing string 'id'")
                continue
            if ev_id in evidence_map:
                errors.append(f"Duplicate evidence ID: {ev_id!r}")
            evidence_map[ev_id] = ev

            # Referential integrity to turn
            ref_turn = str(ev.get("turn_id"))
            if ref_turn not in turn_map:
                errors.append(f"Evidence {ev_id} references non-existent turn_id: {ref_turn!r}")

    # 9. Review validation (nested allowlist)
    review = data.get("review")
    if not isinstance(review, dict) or not review.get("id") or not review.get("author") or not review.get("role"):
        errors.append("Example must have valid 'review' dict with id, author, role, and reviewed_at")
    else:
        rev_extra = set(review.keys()) - REVIEW_ALLOWLIST
        if rev_extra:
            errors.append(f"Review has disallowed keys: {sorted(rev_extra)}")
    review_id = review.get("id") if isinstance(review, dict) else None

    # 10. Judge validation (nested allowlist if present)
    judge = data.get("judge")
    if judge is not None:
        if not isinstance(judge, dict):
            errors.append("'judge' must be null or dict")
        else:
            judge_extra = set(judge.keys()) - JUDGE_ALLOWLIST
            if judge_extra:
                errors.append(f"Judge has disallowed keys: {sorted(judge_extra)}")

    # 11. Findings & Quote Substring Verification (nested allowlist)
    findings = data.get("findings", [])
    if not isinstance(findings, list) or len(findings) == 0:
        errors.append("Example must define at least one finding")
    else:
        for idx, f in enumerate(findings):
            if not isinstance(f, dict):
                errors.append(f"Finding [{idx}] must be dict")
                continue
            f_extra = set(f.keys()) - FINDING_ALLOWLIST
            if f_extra:
                errors.append(f"Finding [{idx}] has disallowed keys: {sorted(f_extra)}")

            fid = f.get("id", f"finding-{idx}")

            # Criterion reference
            cid = f.get("criterion_id")
            if cid not in criteria_map:
                errors.append(f"Finding {fid} references non-existent criterion_id: {cid!r}")

            # Disposition
            disp = f.get("disposition")
            if disp not in {"supported", "issue", "not_assessed"}:
                errors.append(f"Finding {fid} invalid disposition: {disp!r}")

            # Turn references
            t_refs = [str(x) for x in f.get("turn_ids", [])]
            if not t_refs:
                errors.append(f"Finding {fid} must reference at least one turn_id")
            for tr in t_refs:
                if tr not in turn_map:
                    errors.append(f"Finding {fid} references non-existent turn_id: {tr!r}")

            # Evidence references
            ev_refs = f.get("evidence_ids", [])
            for er in ev_refs:
                if er not in evidence_map:
                    errors.append(f"Finding {fid} references non-existent evidence_id: {er!r}")

            # Review reference
            if f.get("review_id") != review_id:
                errors.append(f"Finding {fid} review_id {f.get('review_id')!r} does not match example review.id {review_id!r}")

            # Exact quote matching
            quotes = f.get("quote_references", [])
            for q_idx, quote in enumerate(quotes):
                if not isinstance(quote, str) or not quote.strip():
                    errors.append(f"Finding {fid} quote [{q_idx}] must be non-empty string")
                    continue

                matched = False
                for tr in t_refs:
                    if tr in turn_map:
                        turn_data = turn_map[tr]
                        if quote in turn_data.get("clara_text", "") or quote in turn_data.get("student_text", ""):
                            matched = True
                            break
                if not matched:
                    for er in ev_refs:
                        if er in evidence_map:
                            if quote in evidence_map[er].get("excerpt", ""):
                                matched = True
                                break

                if not matched:
                    errors.append(f"Finding {fid} quote {quote!r} does not match any referenced turn or evidence text verbatim")

    return errors


def validate_publication_readiness(data: dict[str, Any]) -> list[str]:
    """Gatekeeper check: reject publication of unreviewed or self-reviewed findings."""
    errors: list[str] = []
    review = data.get("review", {})
    role = review.get("role", "")
    if role == "implementer_self_review":
        errors.append("Example review role is 'implementer_self_review'; requires independent reviewer approval before public deployment")
    elif role not in {"independent_reviewer", "external_evaluator"}:
        errors.append(f"Review role {role!r} is not an authorized publication reviewer role")
    return errors


def convert_pcm_to_wav(pcm_bytes: bytes, wav_path: Path, sample_rate: int = 24000, channels: int = 1) -> None:
    """Convert raw 16-bit PCM bytes to standard RIFF/WAV."""
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)


def _format_structured_val(v: Any) -> str:
    """Deterministically stringify booleans and numbers."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    return str(v)


def verify_evidence_against_trace(
    evidence_list: list[dict[str, Any]],
    trace_turns: list[dict[str, Any]],
) -> list[str]:
    """Strictly verify each evidence item against recorded tool executions in the trace.

    Binds evidence to a specific tool in the turn and specifically checks tool results,
    rejecting wrong tools, argument-only text, and ungrounded excerpts.
    """
    errors: list[str] = []

    for ev in evidence_list:
        ev_id = ev.get("id", "unknown")
        turn_str = str(ev.get("turn_id"))
        tool_name = ev.get("tool_name")
        excerpt = ev.get("excerpt", "")

        try:
            t_idx = int(turn_str) - 1
            if t_idx < 0 or t_idx >= len(trace_turns):
                errors.append(f"Evidence {ev_id} turn_id {turn_str!r} out of range in trace")
                continue
            turn_obj = trace_turns[t_idx]
        except ValueError:
            errors.append(f"Evidence {ev_id} invalid turn_id {turn_str!r}")
            continue

        tools = turn_obj.get("tools", [])
        matching_tools = [t for t in tools if t.get("name") == tool_name]
        if not matching_tools:
            errors.append(f"Evidence {ev_id} references tool {tool_name!r} in turn {turn_str}, but no tool named {tool_name!r} was called in that turn")
            continue

        target_tool = matching_tools[0]
        args = target_tool.get("args") or {}
        result = target_tool.get("result") or {}

        # Check if excerpt is an argument-only negative match
        args_json = json.dumps(args, ensure_ascii=False)

        # 1. Field path match if specified: MUST match without fallback
        field_path = ev.get("field_path")
        if field_path:
            if not isinstance(result, dict):
                errors.append(f"Evidence {ev_id} specifies field_path {field_path!r}, but result is not a dictionary in turn {turn_str}")
                continue

            parts = field_path.replace("[", ".").replace("]", "").split(".")
            curr = result
            found_field = True
            for part in parts:
                if not part:
                    continue
                if isinstance(curr, dict) and part in curr:
                    curr = curr[part]
                elif isinstance(curr, list) and part.isdigit() and int(part) < len(curr):
                    curr = curr[int(part)]
                else:
                    found_field = False
                    break

            if not found_field:
                errors.append(f"Evidence {ev_id} field_path {field_path!r} does not exist in recorded tool result for {tool_name} in turn {turn_str}")
                continue

            val_str = _format_structured_val(curr)
            if excerpt == val_str or excerpt in val_str:
                # Validated strictly against explicit field_path
                continue
            else:
                errors.append(f"Evidence {ev_id} excerpt {excerpt!r} does not match value at field_path {field_path!r} ({val_str!r}) in turn {turn_str}")
                continue

        # 2. When no field_path is specified:
        matched = False

        # String substring search across all strings in tool result
        def extract_strings(val: Any) -> list[str]:
            out = []
            if isinstance(val, str):
                out.append(val)
            elif isinstance(val, dict):
                for v in val.values():
                    out.extend(extract_strings(v))
            elif isinstance(val, list):
                for item in val:
                    out.extend(extract_strings(item))
            return out

        for s in extract_strings(result):
            if excerpt in s:
                matched = True
                break

        # 3. Deterministic structured key-value match: requires ALL comma-separated segments to be valid key: value pairs
        if not matched and isinstance(result, dict) and "," in excerpt or (":" in excerpt and not excerpt.startswith("http")):
            raw_segments = [p.strip() for p in excerpt.split(",") if p.strip()]
            if raw_segments and all(":" in p for p in raw_segments):
                all_pairs_matched = True
                for p in raw_segments:
                    k, v = p.split(":", 1)
                    k = k.strip()
                    v = v.strip()
                    if k in result:
                        actual_str = _format_structured_val(result[k])
                        if actual_str != v:
                            all_pairs_matched = False
                            break
                    else:
                        all_pairs_matched = False
                        break
                if all_pairs_matched:
                    matched = True

        if not matched:
            if excerpt in args_json:
                errors.append(f"Evidence {ev_id} excerpt {excerpt!r} appears only in tool arguments, not in recorded tool result")
            else:
                errors.append(f"Evidence {ev_id} excerpt {excerpt!r} does not match recorded tool result for {tool_name} in turn {turn_str}")

    return errors


def export_showcase_recording(
    run_dir: Path,
    scenario_id: str,
    output_dir: Path,
    metadata_overrides: dict[str, Any],
) -> dict[str, Any]:
    """Export a run's scenario to an allowlisted showcase directory, validating evidence excerpts against trace tool output."""
    manifest_path = run_dir / "manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # Find the trace file
    trace_path = None
    trace_data = None
    for p in sorted(run_dir.glob("trace-*.json")):
        with open(p, "r", encoding="utf-8") as f:
            t = json.load(f)
            if t.get("scenario_id") == scenario_id:
                trace_path = p
                trace_data = t
                break

    if not trace_path or trace_data is None:
        raise FileNotFoundError(f"Scenario {scenario_id} not found in {run_dir}")

    # Compute trace SHA256
    with open(trace_path, "rb") as f:
        trace_sha256 = hashlib.sha256(f.read()).hexdigest()

    trace_turns = trace_data.get("turns", [])

    # Strictly verify all evidence against tool output in trace
    evidence_errors = verify_evidence_against_trace(
        metadata_overrides.get("evidence", []),
        trace_turns,
    )
    if evidence_errors:
        raise ShowcaseValidationError(evidence_errors)

    # Build audio mapping from observations
    audio_files = trace_data.get("observations", {}).get("audio_files", [])
    turn_audio_map = {item["turn"]: item["path"] for item in audio_files if "turn" in item and "path" in item}

    # Prepare destination with containment verification
    resolved_out = output_dir.resolve()
    scenario_dest = (output_dir / scenario_id).resolve()
    if not scenario_dest.is_relative_to(resolved_out):
        raise ValueError(f"Scenario destination escapes output directory: {scenario_id!r}")
    scenario_dest.mkdir(parents=True, exist_ok=True)

    turns_out = []
    for idx, turn in enumerate(trace_turns):
        tid = str(idx + 1)
        pcm_rel = turn_audio_map.get(tid)
        if not pcm_rel:
            raise ValueError(f"Missing PCM audio mapping for turn {tid}")

        pcm_full = (run_dir / pcm_rel).resolve()
        if not pcm_full.is_relative_to(run_dir.resolve()):
            raise ValueError(f"PCM audio path escapes run_dir: {pcm_rel!r}")
        if not pcm_full.is_file():
            raise FileNotFoundError(f"PCM file not found: {pcm_full}")

        wav_filename = f"turn-{tid}.wav"
        wav_dest = scenario_dest / wav_filename

        with open(pcm_full, "rb") as pf:
            convert_pcm_to_wav(pf.read(), wav_dest)

        # Get audio duration
        with wave.open(str(wav_dest), "rb") as wf:
            dur = round(wf.getnframes() / float(wf.getframerate()), 2)

        turns_out.append({
            "id": tid,
            "student_text": turn.get("user", ""),
            "clara_text": turn.get("assistant", ""),
            "audio_url": wav_filename,
            "duration_seconds": dur,
        })

    # Assemble example.json
    example_dict: dict[str, Any] = {
        "schema_version": "1.0",
        "id": scenario_id,
        "title": metadata_overrides.get("title", scenario_id),
        "summary": metadata_overrides.get("summary", ""),
        "student_goal": metadata_overrides.get("student_goal", ""),
        "model_id": manifest.get("target", {}).get("model", ""),
        "captured_at_utc": manifest.get("started_at", ""),
        "application_revision": manifest.get("git", {}).get("revision", ""),
        "application_source_sha256": metadata_overrides.get("application_source_sha256", ""),
        "environment_label": "Local read-only evaluation with fictional catalogue",
        "source_run_id": manifest.get("run_id", ""),
        "source_trace_sha256": trace_sha256,
        "input_kind": "scripted_text",
        "audio_kind": "captured_model_output",
        "criteria": metadata_overrides.get("criteria", []),
        "turns": turns_out,
        "evidence": metadata_overrides.get("evidence", []),
        "findings": metadata_overrides.get("findings", []),
        "review": metadata_overrides.get("review", {}),
        "judge": metadata_overrides.get("judge", None),
        "limitations": metadata_overrides.get("limitations", []),
    }

    # Validate before saving
    errors = validate_example(example_dict, base_dir=scenario_dest)
    if errors:
        raise ShowcaseValidationError(errors)

    out_file = scenario_dest / "example.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(example_dict, f, indent=2, ensure_ascii=False)

    return example_dict


def main() -> None:
    parser = argparse.ArgumentParser(description="Showcase export and validator")
    subparsers = parser.add_subparsers(dest="command")

    val_parser = subparsers.add_parser("validate", help="Validate catalog or example json")
    val_parser.add_argument("path", type=str, help="Path to catalog.json or example.json")
    val_parser.add_argument("--gate", action="store_true", help="Check publication readiness gate")

    args = parser.parse_args()
    if args.command == "validate":
        p = Path(args.path).resolve()
        if not p.is_file():
            print(f"File not found: {p}", file=sys.stderr)
            sys.exit(1)

        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)

        if "entries" in data:
            errs = validate_catalog(data, base_dir=p.parent, check_gate=args.gate)
        else:
            errs = validate_example(data, base_dir=p.parent)
            if args.gate and not errs:
                errs = validate_publication_readiness(data)

        if errs:
            print(f"Validation FAILED ({len(errs)} errors):", file=sys.stderr)
            for e in errs:
                print(f"  - {e}", file=sys.stderr)
            sys.exit(1)
        else:
            print(f"OK: {p.name} validated cleanly.")
            sys.exit(0)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
