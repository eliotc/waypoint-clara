"""Explicit database selection for legacy suites that can create bookings."""
import os
from urllib.parse import urlsplit


def configure_evaluation_database() -> None:
    candidate = os.environ.get("EVAL_DATABASE_URL", "")
    if not candidate:
        raise ValueError("Set EVAL_DATABASE_URL to a disposable evaluation database; application DATABASE_URL is not used by default")
    parsed = urlsplit(candidate)
    if parsed.scheme not in ("postgres", "postgresql") or not parsed.hostname or parsed.path in ("", "/"):
        raise ValueError("EVAL_DATABASE_URL must be a PostgreSQL URL naming a database")
    app = urlsplit(os.environ.get("DATABASE_URL", ""))
    if (parsed.hostname, parsed.port or 5432, parsed.path) == (app.hostname, app.port or 5432, app.path):
        raise ValueError("EVAL_DATABASE_URL must differ from the application's database")
    # This prevents accidental default use, not aliases/proxies to the same DB.
    # The operator must provision a disposable database and discard it afterwards.
    os.environ["DATABASE_URL"] = candidate
