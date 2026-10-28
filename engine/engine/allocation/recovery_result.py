from dataclasses import dataclass
from enum import Enum

from engine.allocation.carved_artifact import CarvedArtifact


class RecoveryStatus(str, Enum):
    RECOVERED = "RECOVERED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    ALLOCATED_CROSSING = "ALLOCATED_CROSSING"
    FRAGMENTED_UNSUPPORTED = "FRAGMENTED_UNSUPPORTED"
    RECOVERY_FAILED = "RECOVERY_FAILED"


@dataclass(frozen=True)
class RecoveryResult:
    status: RecoveryStatus
    artifact: CarvedArtifact | None = None
    reason: str = ""

    def __post_init__(self):
        if not isinstance(self.status, RecoveryStatus):
            raise TypeError(
                "status must be a RecoveryStatus"
            )

        if self.artifact is not None and not isinstance(
            self.artifact,
            CarvedArtifact,
        ):
            raise TypeError(
                "artifact must be a CarvedArtifact or None"
            )

        if not isinstance(self.reason, str):
            raise TypeError(
                "reason must be a string"
            )

        if self.status == RecoveryStatus.RECOVERED:
            if self.artifact is None:
                raise ValueError(
                    "RECOVERED result requires an artifact"
                )

        if self.status != RecoveryStatus.RECOVERED:
            if self.artifact is not None:
                raise ValueError(
                    "Only RECOVERED results may contain an artifact"
                )

        if not self.reason.strip():
            raise ValueError(
                "reason cannot be empty"
            )

    @property
    def recovered(self):
        return self.status == RecoveryStatus.RECOVERED