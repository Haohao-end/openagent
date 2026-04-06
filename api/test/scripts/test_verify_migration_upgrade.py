from __future__ import annotations

import contextlib
import importlib.util
from pathlib import Path

import pytest


def _load_script_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "verify_migration_upgrade.py"
    spec = importlib.util.spec_from_file_location("verify_migration_upgrade", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeConnection:
    pass


class _FakeEngine:
    def __init__(self):
        self.connect_calls = 0

    @contextlib.contextmanager
    def connect(self):
        self.connect_calls += 1
        yield _FakeConnection()


class _FakeDB:
    def __init__(self):
        self.engine = _FakeEngine()


class _FakeApp:
    @contextlib.contextmanager
    def app_context(self):
        yield self


class _FakeScriptDirectory:
    def __init__(self, heads):
        self._heads = heads

    def get_heads(self):
        return self._heads


class _FakeMigrationContext:
    def __init__(self, revision):
        self._revision = revision

    def get_current_revision(self):
        return self._revision


def test_main_should_upgrade_to_single_head(monkeypatch):
    module = _load_script_module()
    calls = []

    def _load_runtime_dependencies():
        return (lambda: calls.append("load_env"), _FakeApp(), _FakeDB())

    monkeypatch.setattr(module, "_load_runtime_dependencies", _load_runtime_dependencies)
    monkeypatch.setattr(module, "ScriptDirectory", lambda _path: _FakeScriptDirectory(["b1c2d3e4f5a6"]))
    monkeypatch.setattr(module, "upgrade", lambda **kwargs: calls.append(("upgrade", kwargs)))
    monkeypatch.setattr(module.MigrationContext, "configure", lambda _conn: _FakeMigrationContext("b1c2d3e4f5a6"))

    assert module.main() == 0
    assert calls == [
        "load_env",
        ("upgrade", {"directory": str(module.MIGRATION_DIR), "revision": "head"}),
    ]


def test_main_should_fail_when_multiple_heads_exist(monkeypatch):
    module = _load_script_module()

    monkeypatch.setattr(
        module,
        "_load_runtime_dependencies",
        lambda: (lambda: None, _FakeApp(), _FakeDB()),
    )
    monkeypatch.setattr(module, "ScriptDirectory", lambda _path: _FakeScriptDirectory(["a", "b"]))

    with pytest.raises(RuntimeError, match="Expected exactly one migration head"):
        module.main()
