import importlib.util
from pathlib import Path

from alembic.script import ScriptDirectory
from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa


def test_migration_is_connected_to_the_current_single_head():
    migration_dir = Path(__file__).resolve().parents[3] / "internal" / "migration"
    script = ScriptDirectory(str(migration_dir))

    assert script.get_heads() == ["a6b7c8d9e0f1"]
    assert script.get_revision("a6b7c8d9e0f1").down_revision == "f9a1b2c3d4e5"


def _load_migration():
    path = (
        Path(__file__).resolve().parents[3]
        / "internal"
        / "migration"
        / "versions"
        / "a6b7c8d9e0f1_add_api_key_last_used_at.py"
    )
    spec = importlib.util.spec_from_file_location("api_key_last_used_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_api_key_last_used_migration_adds_nullable_timestamp(monkeypatch):
    migration = _load_migration()
    calls = []
    monkeypatch.setattr(migration.op, "add_column", lambda *args: calls.append(args))

    migration.upgrade()

    assert len(calls) == 1
    table, column = calls[0]
    assert table == "api_key"
    assert column.name == "last_used_at"
    assert column.nullable is True


def test_api_key_last_used_migration_can_be_downgraded(monkeypatch):
    migration = _load_migration()
    calls = []
    monkeypatch.setattr(migration.op, "drop_column", lambda *args: calls.append(args))

    migration.downgrade()

    assert calls == [("api_key", "last_used_at")]


def test_api_key_last_used_migration_supports_upgrade_downgrade_upgrade():
    migration = _load_migration()
    engine = sa.create_engine("sqlite://")

    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE api_key (id INTEGER PRIMARY KEY)"))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        assert "last_used_at" in {column["name"] for column in sa.inspect(connection).get_columns("api_key")}

        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()
        assert "last_used_at" not in {column["name"] for column in sa.inspect(connection).get_columns("api_key")}

        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        assert "last_used_at" in {column["name"] for column in sa.inspect(connection).get_columns("api_key")}

    engine.dispose()
