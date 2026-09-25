"""Test doubles for the platform layer."""

from core.modules.base import (
    Action,
    Category,
    Change,
    ModuleResult,
    ModuleState,
    ModuleStatus,
    RiskLevel,
    SageModule,
    Snapshot,
)
from core.platform.registry_win import RegValue, parse_key, restore


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


class FakeRegistryModule(SageModule):
    """Module that sets two DWORDs in an InMemoryRegistry.

    ``fail_after_first_write`` makes apply crash midway, to exercise automatic rollback.
    """

    id = "fake-registry"
    name = "Fake registry tweak"
    description = "Test double"
    category = Category.PRIVACY
    risk_level = RiskLevel.SAFE

    KEY = r"HKLM\SOFTWARE\SageFake"
    TARGETS = {"First": 0, "Second": 0}

    def __init__(self, registry: InMemoryRegistry, fail_after_first_write: bool = False) -> None:
        self.registry = registry
        self.fail_after_first_write = fail_after_first_write
        self.apply_calls = 0

    def status(self) -> ModuleStatus:
        applied = [
            self.registry.read(self.KEY, name) == RegValue.dword(target)
            for name, target in self.TARGETS.items()
        ]
        state = (
            ModuleState.APPLIED
            if all(applied)
            else ModuleState.PARTIAL
            if any(applied)
            else ModuleState.NOT_APPLIED
        )
        return ModuleStatus(module_id=self.id, state=state)

    def capture(self) -> Snapshot:
        return {name: self.registry.read(self.KEY, name) for name in self.TARGETS}

    def apply(self, dry_run: bool = False) -> ModuleResult:
        self.apply_calls += 1
        changes = []
        for name, target in self.TARGETS.items():
            changes.append(
                Change(target=name, before=self.registry.read(self.KEY, name), after=target)
            )
            if not dry_run:
                self.registry.write(self.KEY, name, RegValue.dword(target))
                if self.fail_after_first_write:
                    raise PermissionError("access denied")
        return self.result(Action.APPLY, success=True, dry_run=dry_run, changes=changes)

    def revert(self, snapshot: Snapshot | None = None, dry_run: bool = False) -> ModuleResult:
        changes = []
        for name in self.TARGETS:
            previous = snapshot.get(name) if snapshot else None
            previous = RegValue.model_validate(previous) if previous is not None else None
            changes.append(
                Change(target=name, before=self.registry.read(self.KEY, name), after=previous)
            )
            if not dry_run:
                restore(self.registry, self.KEY, name, previous)
        return self.result(Action.REVERT, success=True, dry_run=dry_run, changes=changes)
