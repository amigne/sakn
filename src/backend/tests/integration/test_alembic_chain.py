"""Test Alembic upgrade → downgrade → upgrade cycle on SQLite.

Unlike the unit-style migration tests that replicate logic manually,
this validates the actual Alembic migration chain end-to-end.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path


def test_alembic_cycle_sqlite() -> None:
    """upgrade head → downgrade base → upgrade head on a fresh SQLite DB."""
    backend_dir = Path(__file__).resolve().parent.parent.parent
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite+aiosqlite:///{db_path}",
        "ENVIRONMENT": "development",
    }
    run_kwargs = {
        "check": True,
        "cwd": str(backend_dir),
        "capture_output": True,
        "text": True,
        "env": env,
        "timeout": 60,
    }

    # Invoke Alembic via `python -m alembic` so the test works regardless of
    # how the venv is laid out (no hardcoded .venv/bin/alembic path).
    alembic_cmd = [sys.executable, "-m", "alembic"]

    try:
        subprocess.run([*alembic_cmd, "upgrade", "head"], **run_kwargs)
        subprocess.run([*alembic_cmd, "downgrade", "base"], **run_kwargs)
        subprocess.run([*alembic_cmd, "upgrade", "head"], **run_kwargs)
    finally:
        Path(db_path).unlink(missing_ok=True)
