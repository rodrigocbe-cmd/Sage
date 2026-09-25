import pytest

from core.platform.registry_win import RegistryError, RegType, RegValue, parse_key, restore
from tests.fakes import InMemoryRegistry

KEY = r"HKLM\SOFTWARE\Policies\Microsoft\Windows\DataCollection"


@pytest.mark.parametrize(
    "key, expected",
    [
        (r"HKLM\SOFTWARE\X", ("HKEY_LOCAL_MACHINE", r"SOFTWARE\X")),
        (r"hkcu\Software\X", ("HKEY_CURRENT_USER", r"Software\X")),
        (r"HKEY_USERS\.DEFAULT\X", ("HKEY_USERS", r".DEFAULT\X")),
        (r"\HKLM\SOFTWARE\X\\", ("HKEY_LOCAL_MACHINE", r"SOFTWARE\X")),
        ("HKLM/SOFTWARE/X", ("HKEY_LOCAL_MACHINE", r"SOFTWARE\X")),
    ],
)
def test_parse_key(key, expected):
    assert parse_key(key) == expected


@pytest.mark.parametrize("key", [r"HKXX\SOFTWARE", "HKLM", "HKLM\\", ""])
def test_parse_key_rejects_bad_paths(key):
    with pytest.raises(RegistryError):
        parse_key(key)


@pytest.mark.parametrize(
    "value",
    [
        RegValue.dword(0),
        RegValue.string("hello"),
        RegValue(type=RegType.BINARY, data=b"\x00\xff\x10"),
        RegValue(type=RegType.MULTI_SZ, data=["a", "b"]),
        RegValue(type=RegType.QWORD, data=2**40),
    ],
)
def test_regvalue_json_roundtrip(value):
    assert RegValue.model_validate_json(value.model_dump_json()) == value


@pytest.mark.parametrize(
    "reg_type, data",
    [
        (RegType.DWORD, "0"),
        (RegType.DWORD, True),
        (RegType.DWORD, -1),
        (RegType.DWORD, 2**32),
        (RegType.SZ, 1),
        (RegType.MULTI_SZ, "a"),
    ],
)
def test_regvalue_rejects_data_not_matching_type(reg_type, data):
    with pytest.raises(ValueError):
        RegValue(type=reg_type, data=data)


def test_restore_writes_previous_value():
    registry = InMemoryRegistry()
    registry.write(KEY, "AllowTelemetry", RegValue.dword(0))

    restore(registry, KEY, "AllowTelemetry", RegValue.dword(3))

    assert registry.read(KEY, "AllowTelemetry") == RegValue.dword(3)


def test_restore_none_deletes_value_that_did_not_exist_before():
    registry = InMemoryRegistry()
    registry.write(KEY, "AllowTelemetry", RegValue.dword(0))

    restore(registry, KEY, "AllowTelemetry", None)

    assert registry.read(KEY, "AllowTelemetry") is None
