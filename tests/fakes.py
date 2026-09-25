"""Test doubles for the platform layer."""

from core.platform.registry_win import RegValue, parse_key


class InMemoryRegistry:
    """RegistryBackend kept in a dict. Case-insensitive, like the real registry."""

    def __init__(self) -> None:
        self.values: dict[tuple[str, str], RegValue] = {}

    @staticmethod
    def _slot(key: str, name: str) -> tuple[str, str]:
        hive, subkey = parse_key(key)
        return f"{hive}\\{subkey}".lower(), name.lower()

    def read(self, key: str, name: str) -> RegValue | None:
        return self.values.get(self._slot(key, name))

    def write(self, key: str, name: str, value: RegValue) -> None:
        self.values[self._slot(key, name)] = value

    def delete(self, key: str, name: str) -> None:
        self.values.pop(self._slot(key, name), None)
