"""Load experiments and write immutable, attributable run evidence."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from importlib.metadata import version
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

from evaluation.adapters import FixtureAdapter
from evaluation.contracts import ROOT, SCHEMA_PATH, asset_path, validate
from evaluation.graders import aggregate, exit_code, grade, STATUSES


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_experiment(path: Path) -> dict:
    path = path.resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError("Experiment must be inside the repository")
    inputs = {p: p.read_bytes() for p in SCHEMA_PATH.parent.glob("*.json")}

    def snapshot(source, kind):
        raw = source.read_bytes()
        value = json.loads(raw)
        validate(value, kind)
        inputs[source] = raw
        return value

    config = snapshot(path, "experiment")

    def load(relative, kind):
        source = asset_path(path.parent, relative)
        return snapshot(source, kind)

    contract_path = asset_path(path.parent, config["contract"])
    inputs[contract_path] = contract_path.read_bytes()
    dataset = load(config["dataset"], "dataset")
    is_live = config['target']['adapter'] == 'clara_live'
    if is_live:
        from evaluation.live_adapter import ClaraLiveAdapter
        adapter = ClaraLiveAdapter(config['target'], dataset['dataset_id'])
    else:
        fixture = load(config['target']['fixture'], 'fixture')
        adapter = FixtureAdapter(fixture)
    cases, ids = [], set()
    for relative in config["scenarios"]:
        scenario_path = asset_path(path.parent, relative)
        scenario = load(relative, "scenario")
        sid = scenario["scenario_id"]
        if sid in ids:
            raise ValueError("Duplicate scenario ID in experiment")
        ids.add(sid)
        persona_path = asset_path(scenario_path.parent, scenario["persona"])
        persona = snapshot(persona_path, "persona")
        check_ids = [check["id"] for check in scenario["checks"]]
        if len(set(check_ids)) != len(check_ids):
            raise ValueError("Duplicate check ID in scenario")
        # Validate coverage and input agreement before creating any run artifacts.
        if not is_live:
            adapter.run(scenario, persona)
        cases.append((scenario, persona))
    if not is_live and ids != set(adapter.traces):
        raise ValueError("Fixture coverage must exactly match the experiment")
    if not is_live and fixture["dataset_id"] != dataset["dataset_id"]:
        raise ValueError("Fixture and dataset IDs differ")
    return {"config": config, "cases": cases, "adapter": adapter, "inputs": inputs}


def git_metadata() -> dict:
    def git(*args):
        result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
        if result.returncode:
            raise OSError("Git metadata unavailable")
        return result.stdout.strip()
    try:
        return {"revision": git("rev-parse", "HEAD"), "dirty": bool(git("status", "--porcelain"))}
    except OSError:
        return {"revision": None, "dirty": None}


def write_json(path: Path, value) -> None:
    with path.open("x") as output:
        json.dump(value, output, indent=2, ensure_ascii=False, allow_nan=False)
        output.write("\n")


def run_experiment(path: Path, out: Path) -> tuple[Path, int]:
    loaded = load_experiment(path)
    config = loaded["config"]
    is_live = config["target"]["adapter"] == "clara_live"
    evidence_kind = "live_text_input" if is_live else "synthetic_fixture"
    schema_version = "1.1" if is_live else "1.0"
    scope = ("Actual Clara Live transport with scripted text input and received audio; not ASR or browser playback validation."
             if is_live else "Harness validation only; no Clara model, voice session or database was exercised.")
    now = datetime.now(timezone.utc)
    run_id = f"{now.strftime('%Y%m%dT%H%M%S%fZ')}-{uuid4().hex[:8]}"
    run_dir = out / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "inputs").mkdir()
    # Snapshot only explicitly referenced assets and toolkit source, never .env.
    inputs = loaded["inputs"]
    for source in (ROOT / "evaluation").glob("*.py"):
        inputs[source] = source.read_bytes()
    inputs[ROOT / "evaluation/requirements.txt"] = (ROOT / "evaluation/requirements.txt").read_bytes()
    if is_live:
        for source in (ROOT / "backend").glob("*.py"):
            inputs[source] = source.read_bytes()
        loaded["adapter"].artifacts = run_dir
    files = []
    for source, content in sorted(inputs.items()):
        sha = digest(content)
        destination = run_dir / "inputs" / sha
        if not destination.exists():
            destination.write_bytes(content)
        files.append({"source": str(source.relative_to(ROOT)), "sha256": sha})
    write_json(run_dir / "manifest.json", {
        "schema_version": schema_version, "run_id": run_id, "started_at": now.isoformat(),
        "experiment_id": config["experiment_id"], "evidence_kind": evidence_kind,
        "target": config["target"], "simulator": "scripted_user_turns" if is_live else "scripted_fixture",
        "grader": "deterministic-equality-and-manual-review-v1",
        "python": sys.version.split()[0], "jsonschema": version("jsonschema"),
        "git": git_metadata(), "inputs": files,
        "scope": scope,
    })
    rows = []
    for repetition in range(1, config["repetitions"] + 1):
        for index, (scenario, persona) in enumerate(loaded["cases"], 1):
            trace_path = f"trace-{repetition}-{index}.json"
            try:
                trace = loaded["adapter"].run(scenario, persona)
                validate(trace, "trace")
                write_json(run_dir / trace_path, trace)
                checks = grade(trace, scenario["checks"])
                row = {"scenario_id": scenario["scenario_id"], "repetition": repetition,
                       "status": aggregate([check["status"] for check in checks]),
                       "checks": checks, "trace": trace_path}
            except Exception as exc:
                # Infrastructure faults never become an agent pass/fail judgment.
                partial = getattr(loaded['adapter'], 'last_trace', None)
                partial_path = None
                if partial is not None:
                    partial_path = f"partial-{repetition}-{index}.json"
                    write_json(run_dir / partial_path, partial)
                row = {"scenario_id": scenario["scenario_id"], "repetition": repetition,
                       "status": "ERROR", "checks": [], "trace": partial_path,
                       "error": (f"LiveProtocolError: {exc}" if type(exc).__name__ == "LiveProtocolError" else type(exc).__name__)}
            rows.append(row)
    counts = Counter(row["status"] for row in rows)
    report = {
        "schema_version": schema_version, "run_id": run_id, "experiment_id": config["experiment_id"],
        "evidence_kind": evidence_kind, "completed_at": datetime.now(timezone.utc).isoformat(),
        "summary": {"total": len(rows), "statuses": {s: counts[s] for s in STATUSES}},
        "results": rows,
    }
    validate(report, "report")
    write_json(run_dir / "report.json", report)
    summary = [f"# {config['experiment_id']} — {run_id}", "",
               scope, "",
               "| Scenario | Repetition | Status |", "|---|---|---|"]
    summary.extend(f"| {r['scenario_id']} | {r['repetition']} | {r['status']} |" for r in rows)
    summary.extend(["", "See report.json for individual checks and manifest.json for input hashes.",
                    "Manual checks remain unresolved; no release decision is automated."])
    (run_dir / "summary.md").write_text("\n".join(summary) + "\n")
    return run_dir, exit_code([row["status"] for row in rows])
