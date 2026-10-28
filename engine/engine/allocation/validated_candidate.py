from dataclasses import dataclass

from engine.allocation.carving_models import SignatureCandidate


@dataclass(frozen=True)
class ValidatedCandidate:
    """
    Represents a signature candidate that has passed
    structural validation.

    This is still NOT a carved file.

    It represents sufficient evidence to proceed
    to the carving stage.
    """

    candidate: SignatureCandidate
    detected_size: int
    validation_reason: str

    def __post_init__(self):

        if not isinstance(
            self.candidate,
            SignatureCandidate,
        ):
            raise TypeError(
                "candidate must be a SignatureCandidate"
            )

        if (
            not isinstance(self.detected_size, int)
            or isinstance(self.detected_size, bool)
        ):
            raise TypeError(
                "detected_size must be an integer"
            )

        if self.detected_size <= 0:
            raise ValueError(
                "detected_size must be greater than zero"
            )

        if not isinstance(
            self.validation_reason,
            str,
        ):
            raise TypeError(
                "validation_reason must be a string"
            )

        if not self.validation_reason.strip():
            raise ValueError(
                "validation_reason cannot be empty"
            )

    @property
    def offset(self):
        return self.candidate.offset

    @property
    def signature(self):
        return self.candidate.signature

    @property
    def extension(self):
        return self.candidate.extension

    @property
    def start_cluster(self):
        return self.candidate.start_cluster

    @property
    def end_cluster(self):
        return self.candidate.end_cluster

    @property
    def confidence(self):
        return self.candidate.confidence