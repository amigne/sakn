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
    alembic_bin = str(backend_dir / ".venv/bin/alembic")
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    try:
        env = {
            **os.environ,
            "DATABASE_URL": f"sqlite+aiosqlite:///{db_path}",
            "ENVIRONMENT": "development",
        }
        subprocess.run(
            [sys.executable, alembic_bin, "upgrade", "head"],
            check=True,
            cwd=str(backend_dir),
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
        )
        subprocess.run(
            [sys.executable, alembic_bin, "downgrade", "base"],
            check=True,
            cwd=str(backend_dir),
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
        )
        subprocess.run(
            [sys.executable, alembic_bin, "upgrade", "head"],
            check=True,
            cwd=str(backend_dir),
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
        )
    finally:
        Path(db_path).unlink(missing_ok=True)
