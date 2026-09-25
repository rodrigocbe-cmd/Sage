"""Runs modules safely: preflight checks, snapshot before apply, rollback on failure, logging.

The CLI (and later the GUI/API) only ever goes through the executor; it never
calls ``module.apply`` or ``module.revert`` directly.

Dry runs skip the preflight and the log: they change nothing, so they work
from a non-elevated terminal.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from core.engine import installer
from core.engine.oplog import OperationLog
from core.engine.rollback import SnapshotStore
from core.modules.base import Action, ModuleResult, ModuleState, ModuleStatus, SageModule


class NoSnapshotError(Exception):
    pass


def default_preflight(data_dir: Path | None) -> Callable[[], None]:
    def check() -> None:
        installer.require_admin()
        installer.require_installed(data_dir)

    return check


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"


class Executor:
    def __init__(
        self,
        data_dir: Path | None = None,
        *,
        store: SnapshotStore | None = None,
        oplog: OperationLog | None = None,
        preflight: Callable[[], None] | None = None,
    ) -> None:
        self.store = store or SnapshotStore(data_dir)
        self.oplog = oplog or OperationLog(data_dir)
        self.preflight = preflight or default_preflight(data_dir)

    def status(self, module: SageModule) -> ModuleStatus:
        try:
            return module.status()
        except Exception as exc:
            return ModuleStatus(
                module_id=module.id, state=ModuleState.UNKNOWN, details=[_describe(exc)]
            )

    def apply(self, module: SageModule, dry_run: bool = False) -> ModuleResult:
        if dry_run:
            return module.apply(dry_run=True)

        self.preflight()
        # Only the first apply captures: later ones would snapshot Sage's own values.
        fresh_snapshot = self.store.active(module.id) is None
        if fresh_snapshot:
            self.store.save(module.id, module.capture())

        try:
            result = module.apply()
        except Exception as exc:
            result = module.result(Action.APPLY, success=False, message=_describe(exc))

        if not result.success and fresh_snapshot:
            result = self._undo_failed_apply(module, result)
        self.oplog.record(result)
        return result

    def revert(
        self, module: SageModule, dry_run: bool = False, to_defaults: bool = False
    ) -> ModuleResult:
        """Undo a module. Uses its snapshot, or the Windows defaults when ``to_defaults``."""
        record = self.store.active(module.id)
        if record is None and not to_defaults:
            raise NoSnapshotError(
                f"No snapshot for {module.id!r}: Sage did not apply it on this machine. "
                "Revert to Windows defaults instead if that is what you want."
            )
        snapshot = None if to_defaults else record.data

        if dry_run:
            return module.revert(snapshot, dry_run=True)

        self.preflight()
        try:
            result = module.revert(snapshot)
        except Exception as exc:
            result = module.result(Action.REVERT, success=False, message=_describe(exc))

        if result.success:
            self.store.archive(module.id)  # also retires a snapshot made moot by to_defaults
        self.oplog.record(result)
        return result

    def revert_all(self, factory: Callable[[str], SageModule]) -> list[ModuleResult]:
        """Revert every module that has an active snapshot, e.g. before uninstalling.

        ``factory`` turns a snapshot's module id into a module (normally ``catalog.create``).
        One failure does not stop the others.
        """
        results = []
        for record in self.store.list_active():
            try:
                module = factory(record.module_id)
            except KeyError:
                results.append(
                    ModuleResult(
                        module_id=record.module_id,
                        action=Action.REVERT,
                        success=False,
                        message="Unknown module in this version of Sage; cannot revert it",
                    )
                )
                continue
            results.append(self.revert(module))
        return results

    def _undo_failed_apply(self, module: SageModule, failed: ModuleResult) -> ModuleResult:
        """An apply failed midway: restore the snapshot taken moments ago."""
        snapshot = self.store.active(module.id)
        try:
            undo = module.revert(snapshot.data)
        except Exception as exc:
            undo = module.result(Action.REVERT, success=False, message=_describe(exc))
        self.oplog.record(undo)

        if undo.success:
            self.store.archive(module.id)
            note = "changes were rolled back automatically"
        else:
            note = f"automatic rollback FAILED ({undo.message}); snapshot kept, run revert"
        return failed.model_copy(update={"message": f"{failed.message} - {note}"})
