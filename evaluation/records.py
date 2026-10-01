"""Evaluation records store and utilities for Waypoint.

Implements the 4 linked records for evaluation outcomes:
1. RunRecord (reconstruct execution conditions, model, environment, git, hashes)
2. AssessmentRecord (evaluator, rubric, outcomes, evidence refs, denominators)
3. IssueRecord (recurring defect tracking, attributed hypotheses, proposed repair)
4. VerificationRecord (adjudication, repair implementation, retest results)
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from evaluation.contracts import validate

ROOT = Path(__file__).resolve().parents[1]
RECORDS_DIR = ROOT / "evaluation" / "records"


def get_git_info(repo_root: Optional[Path] = None) -> tuple[str, bool]:
    root = repo_root or ROOT
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, stderr=subprocess.DEVNULL
        ).decode().strip()
        status = subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=root, stderr=subprocess.DEVNULL
        ).decode().strip()
        return commit, bool(status)
    except Exception:
        return "0000000000000000000000000000000000000000", True


def hash_file(path: Path) -> str:
    if not path.is_file():
        return hashlib.sha256(b"").hexdigest()
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compute_environment_hashes(repo_root: Optional[Path] = None) -> dict[str, Any]:
    root = repo_root or ROOT
    commit, dirty = get_git_info(root)
    
    # Application source hash covers core agent and runtime files
    app_files = (
        root / "backend" / "agent.py",
        root / "backend" / "tools.py",
        root / "backend" / "degree_status.py",
        root / "backend" / "experience_status.py",
        root / "backend" / "suitability.py",
        root / "backend" / "scenarios.py",
    )
    combined = hashlib.sha256()
    for f in app_files:
        if f.is_file():
            combined.update(f.name.encode())
            combined.update(f.read_bytes())
            
    prompt_file = root / "backend" / "agent.py"
    prompt_sha = hash_file(prompt_file)

    seed_file = root / "backend" / "seed.py"
    dataset_sha = hash_file(seed_file)

    return {
        "git_commit": commit,
        "git_dirty": dirty,
        "application_source_sha256": combined.hexdigest(),
        "prompt_sha256": prompt_sha,
        "dataset_version": os.getenv("WAYPOINT_DATASET_VERSION", "clara-local-seed-v2"),
        "dataset_sha256": dataset_sha,
    }


def save_record(record: dict[str, Any], kind: str, base_dir: Optional[Path] = None) -> Path:
    validate(record, kind)
    target_dir = (base_dir or RECORDS_DIR) / f"{kind.split('_')[0]}s"
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # Key id depending on record type
    if kind == "run_record" or record.get("record_type") == "run":
        record_id = record.get("run_id")
    elif kind == "assessment_record" or record.get("record_type") == "assessment":
        record_id = record.get("assessment_id")
    elif kind == "issue_record" or record.get("record_type") == "issue":
        record_id = record.get("issue_id")
    elif kind == "verification_record" or record.get("record_type") == "verification_event":
        record_id = record.get("event_id")
    else:
        record_id = (
            record.get("event_id")
            or record.get("issue_id")
            or record.get("assessment_id")
            or record.get("run_id")
        )
    if not record_id:
        raise ValueError(f"Record missing identifier for {kind}")
        
    out_file = target_dir / f"{record_id}.json"
    if out_file.exists():
        existing_data = json.loads(out_file.read_text())
        if existing_data != record:
            raise ValueError(f"Immutable record collision for {record_id} in {out_file}; cannot overwrite with different payload")
        return out_file
    out_file.write_text(json.dumps(record, indent=2))
    return out_file


def record_showcase_run(trace: dict[str, Any], base_dir: Optional[Path] = None) -> tuple[Optional[Path], Optional[Path]]:
    """
    Transforms a live showcase trace into schema-valid RunRecord and AssessmentRecord,
    persisting them under evaluation/records/.
    """
    run_id = trace.get("run_id")
    if not run_id:
        return None, None

    scenario = trace.get("scenario") or {}
    prov = trace.get("provenance") or {}
    env = compute_environment_hashes()

    created_at_ts = trace.get("created_at") or datetime.now(timezone.utc).timestamp()
    iso_time = datetime.fromtimestamp(created_at_ts, tz=timezone.utc).isoformat()

    raw_trace_path = f"/tmp/waypoint-showcase-runs/{run_id}.json"
    raw_trace_sha = hashlib.sha256(json.dumps(trace, default=str).encode()).hexdigest()

    run_record = {
        "schema_version": "1.0",
        "record_type": "run",
        "run_id": run_id,
        "started_at": iso_time,
        "completed_at": iso_time,
        "status": trace.get("status", "completed"),
        "target": {
            "agent_name": "clara",
            "model_id": prov.get("model_id", "gemini-3.8-live"),
            "runtime": "showcase-live-websocket",
        },
        "environment": env,
        "scenario": {
            "scenario_id": scenario.get("id", "returning-to-study"),
            "version": str(scenario.get("version", "2.0.0")),
            "name": scenario.get("name", "Returning to Study - Cloud Computing Transition"),
            "turn_count": len(scenario.get("student_messages", [])) or trace.get("completed_turns", 6),
        },
        "artifacts": {
            "raw_trace_path": raw_trace_path,
            "raw_trace_sha256": raw_trace_sha,
            "audio_bytes": trace.get("audio_bytes"),
        },
    }

    run_path = save_record(run_record, "run_record", base_dir=base_dir)

    findings = trace.get("findings")
    assessment_path = None
    if isinstance(findings, list) and findings:
        results = []
        for idx, item in enumerate(findings):
            cid = item.get("criterion_id", f"criterion_{idx}")
            st = item.get("status", "unable_to_assess")
            if st == "supported":
                outcome = "pass"
                sev = "none"
            elif st == "issue_observed":
                outcome = "issue_observed"
                sev = "major" if cid == "grounded_advice" else "medium"
            elif st == "unable_to_assess":
                outcome = "unable_to_assess"
                sev = "none"
            else:
                outcome = "execution_error"
                sev = "medium"

            summary = item.get("summary", "")
            tags = []
            s_lower = summary.lower()
            if "contradict" in s_lower or "not online" in s_lower:
                tags.append("catalog_contradiction")
            if "unsupported" in s_lower:
                tags.append("ungrounded_fact")
            if outcome == "unable_to_assess" or "unverified" in s_lower:
                tags.append("missing_evidence")
            if outcome == "pass":
                tags.append("fidelity" if "fact" in cid else "compliance")
            if not tags:
                tags.append("general")

            evidence_refs = []
            for ev in item.get("evidence", []):
                evidence_refs.append({
                    "artifact_id": raw_trace_path,
                    "artifact_sha256": raw_trace_sha,
                    "location": {"turn_id": ev.get("id")},
                    "citation_path": f"/evidence/{ev.get('id', '')}",
                    "excerpt": str(ev.get("quote", "")) if ev.get("quote") is not None else None,
                })

            results.append({
                "result_id": f"res-{run_id}-{idx+1}",
                "criterion_id": cid,
                "outcome": outcome,
                "severity": sev,
                "summary": summary,
                "evidence_refs": evidence_refs,
                "tags": tags,
                "issue_id": None,
            })

        passes = sum(1 for r in results if r["outcome"] == "pass")
        issues = sum(1 for r in results if r["outcome"] == "issue_observed")
        incomplete = sum(1 for r in results if r["outcome"] == "unable_to_assess")
        errors = sum(1 for r in results if r["outcome"] == "execution_error")

        from backend.showcase_judge import SHOWCASE_JUDGE_MODEL

        judge_rubric_file = ROOT / "backend" / "showcase_judge.py"
        rubric_hash = hash_file(judge_rubric_file)

        assessment_record = {
            "schema_version": "1.0",
            "record_type": "assessment",
            "assessment_id": f"assessment-{run_id}",
            "run_id": run_id,
            "assessed_at": iso_time,
            "evaluator": {
                "kind": "model",
                "reviewer_role": "automated_judge",
                "model_id": SHOWCASE_JUDGE_MODEL or "gemini-3.8-flash",
                "rubric_version": "showcase-judge-v2.1",
                "configuration_hash": rubric_hash,
            },
            "supersedes_assessment_id": None,
            "denominators": {
                "total_opportunities": len(results),
                "passes": passes,
                "issues": issues,
                "incomplete": incomplete,
                "execution_errors": errors,
            },
            "results": results,
        }
        assessment_path = save_record(assessment_record, "assessment_record", base_dir=base_dir)

    return run_path, assessment_path


def calculate_metrics(assessments: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Calculate meaningful evaluation metrics accounting for denominators and incomplete checks.
    
    Error counts need denominators: ten failures out of twenty opportunities means something
    fundamentally different from ten out of two thousand.
    """
    total_opportunities = 0
    total_passes = 0
    total_issues = 0
    total_incomplete = 0
    total_errors = 0

    issues_by_criterion: dict[str, int] = {}
    issues_by_tag: dict[str, int] = {}

    for a in assessments:
        denoms = a.get("denominators", {})
        total_opportunities += denoms.get("total_opportunities", 0)
        total_passes += denoms.get("passes", 0)
        total_issues += denoms.get("issues", 0)
        total_incomplete += denoms.get("incomplete", 0)
        total_errors += denoms.get("execution_errors", 0)

        for res in a.get("results", []):
            if res.get("outcome") == "issue_observed":
                crit = res.get("criterion_id", "unknown")
                issues_by_criterion[crit] = issues_by_criterion.get(crit, 0) + 1
                for tag in res.get("tags", []):
                    issues_by_tag[tag] = issues_by_tag.get(tag, 0) + 1

    decided_checks = total_passes + total_issues
    failure_rate_of_evaluated = (total_issues / decided_checks) if decided_checks > 0 else 0.0
    coverage_rate = (decided_checks / total_opportunities) if total_opportunities > 0 else 0.0
    incomplete_rate = (total_incomplete / total_opportunities) if total_opportunities > 0 else 0.0

    return {
        "total_opportunities": total_opportunities,
        "passes": total_passes,
        "issues": total_issues,
        "incomplete": total_incomplete,
        "execution_errors": total_errors,
        "coverage_rate": round(coverage_rate, 4),
        "incomplete_rate": round(incomplete_rate, 4),
        "failure_rate_of_evaluated": round(failure_rate_of_evaluated, 4),
        "issues_by_criterion": issues_by_criterion,
        "issues_by_tag": issues_by_tag,
    }
