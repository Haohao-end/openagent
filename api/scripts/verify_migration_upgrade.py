#!/usr/bin/env python3
"""Verify that the Alembic migration head can be upgraded on the real database."""

from __future__ import annotations

import sys
from pathlib import Path

from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from flask_migrate import upgrade
from sqlalchemy.exc import OperationalError


API_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_DIR = API_ROOT / "internal" / "migration"


def _load_runtime_dependencies():
    sys.path.insert(0, str(API_ROOT))
    from app.http.app import app
    from internal.extension.database_extension import db
    from pkg.env_loader import load_project_env

    return load_project_env, app, db


def main() -> int:
    load_project_env, app, db = _load_runtime_dependencies()
    load_project_env()

    script = ScriptDirectory(str(MIGRATION_DIR))
    heads = script.get_heads()
    if len(heads) != 1:
        raise RuntimeError(f"Expected exactly one migration head, got {heads}")

    with app.app_context():
        try:
            upgrade(directory=str(MIGRATION_DIR), revision="head")
        except OperationalError as exc:
            raise RuntimeError(
                "Database upgrade verification failed because the database connection could not be established. "
                "Check api/.env and ensure the target PostgreSQL instance is running."
            ) from exc

        with db.engine.connect() as connection:
            current_revision = MigrationContext.configure(connection).get_current_revision()

    if current_revision != heads[0]:
        raise RuntimeError(
            f"Migration upgrade did not reach head: current={current_revision}, expected={heads[0]}"
        )

    print(f"Migration upgrade verified at head: {current_revision}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
