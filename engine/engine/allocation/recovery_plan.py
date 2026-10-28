from dataclasses import dataclass

from engine.allocation.validated_candidate import ValidatedCandidate


@dataclass(frozen=True)
class RecoveryPlan:
    """
    Defines exactly what bytes a validated unallocated-space
    candidate is permitted to recover.

    RecoveryPlan is a forensic decision object.

    It does NOT:
        - read image data
        - carve bytes
        - write recovered files
        - create evidence objects

    It only describes the recovery operation.
    """

    candidate: ValidatedCandidate
    source_offset: int
    requested_size: int
    contiguous: bool = True

    def __post_init__(self):
        if not isinstance(self.candidate, ValidatedCandidate):
            raise TypeError(
                "candidate must be a ValidatedCandidate"
            )

        if not isinstance(self.source_offset, int):
            raise TypeError(
                "source_offset must be an integer"
            )

        if self.source_offset < 0:
            raise ValueError(
                "source_offset cannot be negative"
            )

        if not isinstance(self.requested_size, int):
            raise TypeError(
                "requested_size must be an integer"
            )

        if self.requested_size <= 0:
            raise ValueError(
                "requested_size must be greater than zero"
            )

        if not isinstance(self.contiguous, bool):
            raise TypeError(
                "contiguous must be a boolean"
            )

        if self.source_offset != self.candidate.offset:
            raise ValueError(
                "source_offset must match candidate offset"
            )

        if self.requested_size != self.candidate.detected_size:
            raise ValueError(
                "requested_size must match candidate detected_size"
            )