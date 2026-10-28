from dataclasses import dataclass

from engine.allocation.validated_candidate import ValidatedCandidate


@dataclass(frozen=True)
class CarvedArtifact:
    """
    Represents bytes successfully recovered from an unallocated-space
    validated candidate.

    This is a recovered artifact, not an allocation-state object.
    """

    candidate: ValidatedCandidate
    data: bytes
    source_offset: int
    size: int

    def __post_init__(self):
        if not isinstance(self.candidate, ValidatedCandidate):
            raise TypeError(
                "candidate must be a ValidatedCandidate"
            )

        if not isinstance(self.data, bytes):
            raise TypeError(
                "data must be bytes"
            )

        if not isinstance(self.source_offset, int):
            raise TypeError(
                "source_offset must be an integer"
            )

        if self.source_offset < 0:
            raise ValueError(
                "source_offset cannot be negative"
            )

        if not isinstance(self.size, int):
            raise TypeError(
                "size must be an integer"
            )

        if self.size <= 0:
            raise ValueError(
                "size must be greater than zero"
            )

        if self.size != len(self.data):
            raise ValueError(
                "size must match the length of data"
            )

        if self.source_offset != self.candidate.offset:
            raise ValueError(
                "source_offset must match candidate offset"
            )

        if self.size != self.candidate.detected_size:
            raise ValueError(
                "size must match candidate detected_size"
            )

    @property
    def signature(self):
        return self.candidate.signature

    @property
    def extension(self):
        return self.candidate.extension

    @property
    def confidence(self):
        return self.candidate.confidence

    @property
    def start_cluster(self):
        return self.candidate.start_cluster

    @property
    def end_cluster(self):
        return self.candidate.end_cluster