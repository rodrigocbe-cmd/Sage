"""Windows registry access.

Modules talk to the registry through the ``RegistryBackend`` protocol, never to
``winreg`` directly. ``WinRegistry`` is the real implementation; tests swap in an
in-memory fake so they can run without touching the machine.

Keys are written as full paths with a hive prefix, e.g.
``HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\DataCollection``. All access goes
through the 64-bit registry view so a 32-bit Python still sees the real keys.
"""

from __future__ import annotations

import base64
import sys
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator

if sys.platform == "win32":
    import winreg


class RegType(StrEnum):
    SZ = "REG_SZ"
    EXPAND_SZ = "REG_EXPAND_SZ"
    BINARY = "REG_BINARY"
    DWORD = "REG_DWORD"
    MULTI_SZ = "REG_MULTI_SZ"
    QWORD = "REG_QWORD"


# Numeric codes as defined by winreg; kept here so this module imports on any OS.
_TYPE_CODES: dict[RegType, int] = {
    RegType.SZ: 1,
    RegType.EXPAND_SZ: 2,
    RegType.BINARY: 3,
    RegType.DWORD: 4,
    RegType.MULTI_SZ: 7,
    RegType.QWORD: 11,
}
_TYPES_BY_CODE = {code: reg_type for reg_type, code in _TYPE_CODES.items()}

_PY_TYPES: dict[RegType, type] = {
    RegType.SZ: str,
    RegType.EXPAND_SZ: str,
    RegType.BINARY: bytes,
    RegType.DWORD: int,
    RegType.MULTI_SZ: list,
    RegType.QWORD: int,
}
_INT_RANGES = {RegType.DWORD: 2**32, RegType.QWORD: 2**64}

_HIVE_ALIASES = {
    "HKLM": "HKEY_LOCAL_MACHINE",
    "HKCU": "HKEY_CURRENT_USER",
    "HKCR": "HKEY_CLASSES_ROOT",
    "HKU": "HKEY_USERS",
    "HKCC": "HKEY_CURRENT_CONFIG",
}


class RegistryError(Exception):
    pass


class RegValue(BaseModel):
    """A registry value with its type. JSON-serializable, so it can go into a snapshot."""

    model_config = ConfigDict(frozen=True, ser_json_bytes="base64", val_json_bytes="base64")

    type: RegType
    data: str | int | bytes | list[str]

    @field_validator("data", mode="before")
    @classmethod
    def _check_data_matches_type(cls, data: object, info: ValidationInfo) -> object:
        # The union alone is ambiguous (base64 bytes in JSON look like a str), so the
        # declared registry type decides how data is parsed and what it must be.
        reg_type = info.data.get("type")
        if reg_type is RegType.BINARY and isinstance(data, str):
            data = base64.b64decode(data, validate=True)
        if reg_type is None:
            return data  # the type field itself failed validation; pydantic reports that
        expected = _PY_TYPES[reg_type]
        if not isinstance(data, expected) or isinstance(data, bool):
            raise ValueError(f"{reg_type} requires {expected.__name__}, got {type(data).__name__}")
        if reg_type in _INT_RANGES and not 0 <= data < _INT_RANGES[reg_type]:
            raise ValueError(f"{reg_type} out of range: {data}")
        return data

    @classmethod
    def dword(cls, data: int) -> RegValue:
        return cls(type=RegType.DWORD, data=data)

    @classmethod
    def string(cls, data: str) -> RegValue:
        return cls(type=RegType.SZ, data=data)


def parse_key(key: str) -> tuple[str, str]:
    """Split ``HKLM\\Some\\Path`` into (canonical hive name, subkey)."""
    hive, _, subkey = key.replace("/", "\\").strip("\\").partition("\\")
    hive = _HIVE_ALIASES.get(hive.upper(), hive.upper())
    if hive not in _HIVE_ALIASES.values():
        raise RegistryError(f"Unknown registry hive in {key!r}")
    if not subkey:
        raise RegistryError(f"Refusing to operate on a hive root: {key!r}")
    return hive, subkey


class RegistryBackend(Protocol):
    def read(self, key: str, name: str) -> RegValue | None:
        """Return the value, or None if the key or the value does not exist."""
        ...

    def write(self, key: str, name: str, value: RegValue) -> None:
        """Set the value, creating the key if needed."""
        ...

    def delete(self, key: str, name: str) -> None:
        """Remove the value. A missing key or value is not an error."""
        ...


def restore(backend: RegistryBackend, key: str, name: str, previous: RegValue | None) -> None:
    """Put a value back to a captured state, where None means "did not exist"."""
    if previous is None:
        backend.delete(key, name)
    else:
        backend.write(key, name, previous)


class WinRegistry:
    """RegistryBackend backed by the real Windows registry."""

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise RegistryError("WinRegistry is only available on Windows")

    @staticmethod
    def _open(key: str, access: int, create: bool = False):
        hive_name, subkey = parse_key(key)
        hive = getattr(winreg, hive_name)
        access |= winreg.KEY_WOW64_64KEY
        if create:
            return winreg.CreateKeyEx(hive, subkey, 0, access)
        return winreg.OpenKey(hive, subkey, 0, access)

    def read(self, key: str, name: str) -> RegValue | None:
        try:
            with self._open(key, winreg.KEY_READ) as handle:
                data, type_code = winreg.QueryValueEx(handle, name)
        except FileNotFoundError:
            return None
        reg_type = _TYPES_BY_CODE.get(type_code)
        if reg_type is None:
            raise RegistryError(f"Unsupported value type {type_code} at {key}\\{name}")
        return RegValue(type=reg_type, data=data)

    def write(self, key: str, name: str, value: RegValue) -> None:
        with self._open(key, winreg.KEY_SET_VALUE, create=True) as handle:
            winreg.SetValueEx(handle, name, 0, _TYPE_CODES[value.type], value.data)

    def delete(self, key: str, name: str) -> None:
        try:
            with self._open(key, winreg.KEY_SET_VALUE) as handle:
                winreg.DeleteValue(handle, name)
        except FileNotFoundError:
            pass
