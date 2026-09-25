import json

import pytest

from core.engine.executor import Executor, NoSnapshotError
from core.engine.installer import NotElevatedError
from core.modules.base import ModuleState
from core.platform.registry_win import RegValue
from tests.fakes import FakeRegistryModule, InMemoryRegistry

KEY = FakeRegistryModule.KEY


@pytest.fixture
def registry():
    registry = InMemoryRegistry()
    registry.write(KEY, "First", RegValue.dword(5))  # user's own value; "Second" is absent
    return registry


@pytest.fixture
def executor(tmp_path):
    return Executor(tmp_path, preflight=lambda: None)


def log_entries(executor):
    if not executor.oplog.path.exists():
        return []
    return [json.loads(line) for line in executor.oplog.path.read_text("utf-8").splitlines()]


def test_apply_snapshots_first_then_revert_restores_exact_state(executor, registry):
    module = FakeRegistryModule(registry)

    assert executor.apply(module).success
    assert module.status().state is ModuleState.APPLIED
    assert executor.store.active(module.id) is not None

    assert executor.revert(module).success
    assert registry.read(KEY, "First") == RegValue.dword(5)
    assert registry.read(KEY, "Second") is None  # did not exist before, so it is removed
    assert executor.store.active(module.id) is None  # archived


def test_reapply_keeps_original_snapshot(executor, registry):
    module = FakeRegistryModule(registry)
    executor.apply(module)
    executor.apply(module)  # would capture Sage's own values if it re-snapshotted

    executor.revert(module)
    assert registry.read(KEY, "First") == RegValue.dword(5)


def test_failed_apply_is_rolled_back_automatically(executor, registry):
    module = FakeRegistryModule(registry, fail_after_first_write=True)

    result = executor.apply(module)

    assert not result.success
    assert "PermissionError" in result.message and "rolled back" in result.message
    assert registry.read(KEY, "First") == RegValue.dword(5)
    assert executor.store.active(module.id) is None
    assert [e["action"] for e in log_entries(executor)] == ["revert", "apply"]


def test_dry_run_changes_nothing_and_skips_preflight(tmp_path, registry):
    def deny():
        raise NotElevatedError("not admin")

    executor = Executor(tmp_path, preflight=deny)
    module = FakeRegistryModule(registry)

    result = executor.apply(module, dry_run=True)

    assert result.dry_run and len(result.changes) == 2
    assert registry.read(KEY, "First") == RegValue.dword(5)
    assert executor.store.active(module.id) is None
    assert log_entries(executor) == []


def test_preflight_failure_blocks_apply_before_anything_happens(tmp_path, registry):
    def deny():
        raise NotElevatedError("not admin")

    executor = Executor(tmp_path, preflight=deny)
    module = FakeRegistryModule(registry)

    with pytest.raises(NotElevatedError):
        executor.apply(module)
    assert module.apply_calls == 0
    assert executor.store.active(module.id) is None


def test_revert_without_snapshot_requires_explicit_defaults(executor, registry):
    module = FakeRegistryModule(registry)

    with pytest.raises(NoSnapshotError):
        executor.revert(module)

    assert executor.revert(module, to_defaults=True).success
    assert registry.read(KEY, "First") is None


def test_operations_are_logged_with_user(executor, registry):
    module = FakeRegistryModule(registry)
    executor.apply(module)
    executor.revert(module)

    entries = log_entries(executor)
    assert [e["action"] for e in entries] == ["apply", "revert"]
    assert all(e["module_id"] == module.id and e["user"] for e in entries)


def test_status_reports_unknown_instead_of_crashing(executor, registry):
    module = FakeRegistryModule(registry)
    module.status = lambda: 1 / 0

    status = executor.status(module)
    assert status.state is ModuleState.UNKNOWN
    assert "ZeroDivisionError" in status.details[0]


def test_revert_all_reverts_every_snapshot_and_reports_unknown_modules(executor, registry):
    module = FakeRegistryModule(registry)
    executor.apply(module)
    executor.store.save("removed-in-this-version", {})

    results = executor.revert_all(
        lambda module_id: {module.id: module}[module_id]  # KeyError for unknown ids
    )

    by_id = {r.module_id: r for r in results}
    assert by_id[module.id].success
    assert not by_id["removed-in-this-version"].success
    assert registry.read(KEY, "First") == RegValue.dword(5)
    assert [r.module_id for r in executor.store.list_active()] == ["removed-in-this-version"]


def test_revert_all_with_nothing_applied(executor):
    assert executor.revert_all(lambda module_id: None) == []
