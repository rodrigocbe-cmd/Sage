import pytest

from core.modules.base import (
    Action,
    Category,
    Change,
    ModuleState,
    ModuleStatus,
    RiskLevel,
    SageModule,
    Snapshot,
)


class FakeModule(SageModule):
    """In-memory module: toggles a single value in a dict instead of the registry."""

    id = "fake"
    name = "Fake tweak"
    description = "Test double"
    category = Category.PRIVACY
    risk_level = RiskLevel.SAFE

    DEFAULT = 1
    TARGET = 0

    def __init__(self) -> None:
        self.store = {"value": self.DEFAULT}

    def status(self) -> ModuleStatus:
        applied = self.store["value"] == self.TARGET
        return ModuleStatus(
            module_id=self.id,
            state=ModuleState.APPLIED if applied else ModuleState.NOT_APPLIED,
        )

    def capture(self) -> Snapshot:
        return dict(self.store)

    def apply(self, dry_run: bool = False):
        change = Change(target="value", before=self.store["value"], after=self.TARGET)
        if not dry_run:
            self.store["value"] = self.TARGET
        return self.result(Action.APPLY, success=True, dry_run=dry_run, changes=[change])

    def revert(self, snapshot: Snapshot | None = None, dry_run: bool = False):
        restore_to = snapshot["value"] if snapshot else self.DEFAULT
        change = Change(target="value", before=self.store["value"], after=restore_to)
        if not dry_run:
            self.store["value"] = restore_to
        return self.result(Action.REVERT, success=True, dry_run=dry_run, changes=[change])


def test_apply_then_revert_with_snapshot_restores_captured_value():
    module = FakeModule()
    module.store["value"] = 7  # user had a custom value before Sage
    snapshot = module.capture()

    module.apply()
    assert module.status().state is ModuleState.APPLIED

    module.revert(snapshot)
    assert module.store["value"] == 7


def test_revert_without_snapshot_restores_default():
    module = FakeModule()
    module.apply()
    module.revert()
    assert module.store["value"] == FakeModule.DEFAULT


def test_dry_run_reports_changes_without_applying():
    module = FakeModule()
    result = module.apply(dry_run=True)

    assert result.dry_run
    assert result.changes[0].before == 1 and result.changes[0].after == 0
    assert module.status().state is ModuleState.NOT_APPLIED


def test_result_is_json_serializable():
    payload = FakeModule().apply().model_dump_json()
    assert '"module_id":"fake"' in payload
    assert '"action":"apply"' in payload


def test_concrete_module_without_metadata_is_rejected():
    with pytest.raises(TypeError, match="missing module metadata: .*risk_level"):

        class Incomplete(FakeModule.__base__):  # type: ignore[misc]
            id = "incomplete"
            name = "x"
            description = "x"
            category = Category.PRIVACY

            status = FakeModule.status
            capture = FakeModule.capture
            apply = FakeModule.apply
            revert = FakeModule.revert


def test_abstract_intermediate_may_omit_metadata():
    class RegistryModuleBase(SageModule):
        pass  # still abstract: no error

    with pytest.raises(TypeError):
        RegistryModuleBase()  # type: ignore[abstract]
