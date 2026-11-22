from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_module():
    module_path = (
        Path(__file__).resolve().parents[3]
        / "internal"
        / "migration"
        / "versions"
        / "a3b4c5d6e7f8_add_tag_tables.py"
    )
    spec = importlib.util.spec_from_file_location("a3b4c5d6e7f8_add_tag_tables", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeOp:
    def __init__(self):
        self.created_tables = []
        self.created_indexes = []
        self.dropped_tables = []

    def create_table(self, table_name, *columns, **kwargs):
        self.created_tables.append(table_name)

    def create_index(self, index_name, table_name, columns, unique=False):
        self.created_indexes.append((index_name, table_name))

    def drop_table(self, table_name):
        self.dropped_tables.append(table_name)


def test_upgrade_should_create_tag_tables_with_indexes():
    module = _load_module()
    fake_op = _FakeOp()
    monkey_op = fake_op

    import internal.migration.versions.a3b4c5d6e7f8_add_tag_tables as _m  # noqa: F401

    # upgrade uses module-level `op`; patch it via monkeypatching op attribute
    original_op = module.op
    module.op = monkey_op
    try:
        module.upgrade()
    finally:
        module.op = original_op

    assert fake_op.created_tables == ["tag", "app_tag", "workflow_tag"]
    index_tables = {table for _name, table in fake_op.created_indexes}
    assert index_tables == {"tag", "app_tag", "workflow_tag"}


def test_downgrade_should_drop_tables_in_reverse_dependency_order():
    module = _load_module()
    fake_op = _FakeOp()
    original_op = module.op
    module.op = fake_op
    try:
        module.downgrade()
    finally:
        module.op = original_op

    assert fake_op.dropped_tables == ["workflow_tag", "app_tag", "tag"]


def test_revision_chain_should_extend_current_head():
    module = _load_module()
    assert module.revision == "a3b4c5d6e7f8"
    assert module.down_revision == "7ffffccfd101"
