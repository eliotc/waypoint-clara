"""Evidence checks, not an automated claim of counselling quality."""
from __future__ import annotations

STATUSES = ("PASS", "FAIL", "NEEDS_HUMAN", "ERROR", "SKIPPED")


def pointer(document, path: str):
    """Resolve a JSON Pointer, distinguishing an absent field from null."""
    value = document
    if not path:
        return value
    if not path.startswith("/"):
        raise ValueError("Expected a JSON Pointer")
    for token in path[1:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(value, list):
            if not token.isdigit() or (len(token) > 1 and token[0] == "0"):
                raise KeyError(token)
            value = value[int(token)]
        elif isinstance(value, dict):
            value = value[token]
        else:
            raise KeyError(token)
    return value


def aggregate(statuses: list[str]) -> str:
    if not statuses or any(s not in STATUSES for s in statuses):
        return "ERROR"
    # Keep all underlying results; the aggregate is only a conservative summary.
    for status in ("ERROR", "FAIL", "NEEDS_HUMAN", "SKIPPED"):
        if status in statuses:
            return status
    return "PASS"


def exit_code(statuses: list[str]) -> int:
    if not statuses or any(s not in ("PASS", "FAIL") for s in statuses):
        return 2
    return 1 if "FAIL" in statuses else 0


def typed_equal(actual, expected) -> bool:
    if type(actual) is not type(expected):
        return False
    if isinstance(actual, dict):
        return actual.keys() == expected.keys() and all(typed_equal(actual[k], expected[k]) for k in actual)
    if isinstance(actual, list):
        return len(actual) == len(expected) and all(typed_equal(a, b) for a, b in zip(actual, expected))
    return actual == expected


def grade(trace: dict, checks: list[dict]) -> list[dict]:
    results = []
    for check in checks:
        row = {key: check[key] for key in ("id", "criterion", "severity")}
        row["pointer"] = check["pointer"]
        try:
            actual = pointer(trace, check["pointer"])
            if check["operator"] == "manual":
                status, reason = "NEEDS_HUMAN", check["instruction"]
            else:
                expected = check["expected"]
                # Avoid bool == int silently passing a schema/contract mismatch.
                passed = typed_equal(actual, expected)
                status = "PASS" if passed else "FAIL"
                reason = "Evidence matches expected value" if passed else "Evidence differs from expected value"
        except (KeyError, IndexError, ValueError):
            status, reason = "ERROR", "Required evidence is missing or its pointer is invalid"
        row.update(status=status, reason=reason)
        results.append(row)
    # Every completed interaction must have a visible assistant response.
    for index, turn in enumerate(trace["turns"]):
        if not turn["assistant"].strip():
            results.append({
                "id": f"response-{index + 1}", "criterion": "response-completeness",
                "severity": "high", "pointer": f"/turns/{index}/assistant",
                "status": "FAIL", "reason": "Completed turn has an empty assistant response",
            })
    return results
