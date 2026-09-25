from pathlib import Path

import pytest

from core.engine.paths import default_data_dir
from core.engine.rollback import SnapshotError, SnapshotExistsError, SnapshotStore
from core.platform.registry_win import RegType, RegValue


@pytest.fixture
def store(tmp_path):
    return SnapshotStore(tmp_path)


def test_save_and_load_roundtrip_with_regvalues(store):
    data = {
        "AllowTelemetry": RegValue.dword(3),
        "Blob": RegValue(type=RegType.BINARY, data=b"\x00\xff"),
        "Missing": None,
    }
    store.save("telemetry", data)

    loaded = store.active("telemetry").data
    assert RegValue.model_validate(loaded["AllowTelemetry"]) == RegValue.dword(3)
    assert RegValue.model_validate(loaded["Blob"]).data == b"\x00\xff"
    assert loaded["Missing"] is None


def test_active_is_none_when_nothing_saved(store):
    assert store.active("telemetry") is None
    assert store.list_active() == []


def test_second_save_does_not_overwrite_original_state(store):
    store.save("telemetry", {"value": "original"})

    with pytest.raises(SnapshotExistsError):
        store.save("telemetry", {"value": "already-tweaked"})
    assert store.active("telemetry").data == {"value": "original"}

    store.save("telemetry", {"value": "forced"}, overwrite=True)
    assert store.active("telemetry").data == {"value": "forced"}


def test_archive_moves_active_snapshot(store):
    store.save("telemetry", {"value": 1})

    archived = store.archive("telemetry")

    assert archived is not None and archived.exists()
    assert archived.parent == store.archive_dir
    assert store.active("telemetry") is None
    assert store.archive("telemetry") is None  # nothing left to archive


def test_list_active(store):
    store.save("b-module", {})
    store.save("a-module", {})
    assert [r.module_id for r in store.list_active()] == ["a-module", "b-module"]


def test_no_temp_files_left_behind(store):
    store.save("telemetry", {"value": 1})
    assert [p.name for p in store.active_dir.iterdir()] == ["telemetry.json"]


@pytest.mark.parametrize("module_id", ["../evil", "a/b", "", "UPPER", "with space"])
def test_rejects_ids_that_are_not_safe_filenames(store, module_id):
    with pytest.raises(SnapshotError):
        store.save(module_id, {})


def test_corrupted_snapshot_raises_clear_error(store):
    store.save("telemetry", {})
    (store.active_dir / "telemetry.json").write_text("{not json", encoding="utf-8")

    with pytest.raises(SnapshotError, match="corrupted"):
        store.active("telemetry")


def test_default_data_dir(monkeypatch):
    monkeypatch.delenv("SAGE_DATA_DIR", raising=False)
    monkeypatch.setenv("ProgramData", r"C:\ProgramData")
    assert default_data_dir() == Path(r"C:\ProgramData\Sage")

    monkeypatch.setenv("SAGE_DATA_DIR", r"D:\custom")
    assert default_data_dir() == Path(r"D:\custom")
