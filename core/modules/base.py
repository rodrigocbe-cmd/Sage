"""Contract every Sage module implements.

A module owns one tweak end to end: it knows how to read the current state of
what it touches (``capture``/``status``), how to change it (``apply``) and how
to undo it (``revert``). The engine never needs module-specific knowledge; it
only calls these methods, stores the captured snapshot and logs the results.

Lifecycle driven by the executor::

    snapshot = module.capture()       # stored by the rollback engine
    result = module.apply()
    ...
    result = module.revert(snapshot)  # back to exactly how it was
    result = module.revert()          # no snapshot: back to Windows defaults
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, ClassVar

from pydantic import BaseModel, Field


class RiskLevel(StrEnum):
    SAFE = "safe"  # cosmetic or trivially reversible, no functional impact
    MODERATE = "moderate"  # disables a feature someone might use
    ADVANCED = "advanced"  # can break functionality or updates if misused


class Category(StrEnum):
    PRIVACY = "privacy"
    DEBLOAT = "debloat"
    SERVICES = "services"
    POWER = "power"
    GAMING = "gaming"


class ModuleState(StrEnum):
    APPLIED = "applied"  # every change the module makes is in place
    NOT_APPLIED = "not_applied"  # none of the changes are in place
    PARTIAL = "partial"  # some are, some are not (e.g. Windows Update reverted one)
    UNKNOWN = "unknown"  # state could not be read


class Action(StrEnum):
    APPLY = "apply"
    REVERT = "revert"


class Change(BaseModel):
    """One atomic change, e.g. a registry value or a service start type."""

    target: str  # human-readable location, e.g. r"HKLM\...\DataCollection\AllowTelemetry"
    before: Any = None
    after: Any = None
    description: str = ""


class ModuleStatus(BaseModel):
    module_id: str
    state: ModuleState
    details: list[str] = Field(default_factory=list)


class ModuleResult(BaseModel):
    module_id: str
    action: Action
    success: bool
    dry_run: bool = False
    changes: list[Change] = Field(default_factory=list)
    message: str = ""
    reboot_required: bool = False
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


Snapshot = dict[str, Any]
"""JSON-serializable state captured before apply, handed back to revert."""


class SageModule(ABC):
    """Base class for every tweak. Subclasses set the metadata and implement the four methods."""

    id: ClassVar[str]
    name: ClassVar[str]
    description: ClassVar[str]
    category: ClassVar[Category]
    risk_level: ClassVar[RiskLevel]
    reboot_required: ClassVar[bool] = False

    _REQUIRED_ATTRS: ClassVar[tuple[str, ...]] = (
        "id",
        "name",
        "description",
        "category",
        "risk_level",
    )

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # Abstract intermediates are allowed to leave metadata unset. ABCMeta fills
        # __abstractmethods__ only after this hook runs, so check the methods directly.
        if any(getattr(getattr(cls, n, None), "__isabstractmethod__", False) for n in dir(cls)):
            return
        missing = [attr for attr in cls._REQUIRED_ATTRS if not hasattr(cls, attr)]
        if missing:
            raise TypeError(f"{cls.__name__} is missing module metadata: {', '.join(missing)}")

    @abstractmethod
    def status(self) -> ModuleStatus:
        """Report whether the tweak is currently in effect. Must not change anything."""

    @abstractmethod
    def capture(self) -> Snapshot:
        """Return the current value of everything ``apply`` would touch. Read-only."""

    @abstractmethod
    def apply(self, dry_run: bool = False) -> ModuleResult:
        """Make the changes. With ``dry_run`` only report what would change."""

    @abstractmethod
    def revert(self, snapshot: Snapshot | None = None, dry_run: bool = False) -> ModuleResult:
        """Undo the changes.

        With a snapshot, restore exactly the captured values. Without one, restore
        the Windows defaults for everything this module touches.
        """

    def result(self, action: Action, **kwargs: Any) -> ModuleResult:
        """Build a ``ModuleResult`` pre-filled with this module's id and reboot flag."""
        kwargs.setdefault("reboot_required", self.reboot_required)
        return ModuleResult(module_id=self.id, action=action, **kwargs)

    def __repr__(self) -> str:
        return f"<{type(self).__name__} id={self.id!r} risk={self.risk_level.value}>"
