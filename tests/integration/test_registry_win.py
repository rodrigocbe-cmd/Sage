"""Exercises WinRegistry against the real registry, confined to a throwaway HKCU key."""

import sys
import uuid

import pytest

from core.platform.registry_win import RegType, RegValue, WinRegistry

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(sys.platform != "win32", reason="Windows only"),
]


@pytest.fixture
def key():
    import winreg

    subkey = rf"Software\SageTest-{uuid.uuid4().hex}"
    yield rf"HKCU\{subkey}"
    try:
        winreg.DeleteKeyEx(winreg.HKEY_CURRENT_USER, subkey, winreg.KEY_WOW64_64KEY)
    except FileNotFoundError:
        pass


@pytest.mark.parametrize(
    "value",
    [
        RegValue.dword(0),
        RegValue.dword(0xFFFFFFFF),
        RegValue.string("sage"),
        RegValue(type=RegType.EXPAND_SZ, data=r"%SystemRoot%\System32"),
        RegValue(type=RegType.BINARY, data=b"\x01\x02"),
        RegValue(type=RegType.MULTI_SZ, data=["one", "two"]),
        RegValue(type=RegType.QWORD, data=2**40),
    ],
)
def test_write_then_read_roundtrip(key, value):
    registry = WinRegistry()
    registry.write(key, "Value", value)
    assert registry.read(key, "Value") == value


def test_read_missing_key_and_value_returns_none(key):
    registry = WinRegistry()
    assert registry.read(key, "Nope") is None
    registry.write(key, "Exists", RegValue.dword(1))
    assert registry.read(key, "Nope") is None


def test_delete_is_idempotent(key):
    registry = WinRegistry()
    registry.delete(key, "Missing")  # key does not exist yet
    registry.write(key, "Value", RegValue.dword(1))
    registry.delete(key, "Value")
    registry.delete(key, "Value")
    assert registry.read(key, "Value") is None
