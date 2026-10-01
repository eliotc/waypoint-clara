"""Validate versioned JSON assets without importing the application or .env."""
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = Path(__file__).parent / "schemas" / "v1.json"
EVAL_RECORDS_SCHEMA_PATH = Path(__file__).parent / "schemas" / "eval_records_v1.json"


def validate(value: dict, kind: str) -> None:
    version = value.get("schema_version") if isinstance(value, dict) else None
    if kind in ("run_record", "assessment_record", "issue_record", "verification_record"):
        if version != "1.0":
            raise ValueError("Unsupported evaluation records schema version")
        schema = json.loads(EVAL_RECORDS_SCHEMA_PATH.read_text())
    else:
        paths = {"1.0": SCHEMA_PATH, "1.1": SCHEMA_PATH.with_name("v1.1.json")}
        if version not in paths:
            raise ValueError("Unsupported evaluation schema version")
        schema = json.loads(paths[version].read_text())
    validator = Draft202012Validator(
        {"$ref": f"#/$defs/{kind}", "$defs": schema["$defs"]},
        format_checker=FormatChecker(),
    )
    errors = sorted(validator.iter_errors(value), key=lambda e: str(list(e.path)))
    if errors:
        error = errors[0]
        # Do not echo arbitrary input values (which may contain private data).
        location = "/".join(str(p) for p in error.path) or "<root>"
        raise ValueError(f"Invalid {kind} at {location}: {error.validator} constraint")


def asset_path(base: Path, relative: str) -> Path:
    path = (base / relative).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError("Evaluation input must be inside the repository")
    if not path.is_file():
        raise ValueError(f"Missing evaluation asset: {relative}")
    return path


def read_asset(path: Path, kind: str) -> dict:
    data = json.loads(path.read_text())
    validate(data, kind)
    return data
