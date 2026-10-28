from dataclasses import dataclass, field


@dataclass(frozen=True)
class SignatureCandidate:
    """
    A forensic candidate identified by signature detection.

    This object represents a possible file only.

    It does NOT mean that a valid file has been recovered.
    Validation must happen later in the carving pipeline.
    """

    signature: str
    extension: str

    offset: int

    relative_offset: int

    start_cluster: int | None = None
    end_cluster: int | None = None

    confidence: float = 0.0

    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.offset < 0:
            raise ValueError(
                "Candidate offset cannot be negative"
            )

        if self.relative_offset < 0:
            raise ValueError(
                "Relative offset cannot be negative"
            )

        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                "Confidence must be between 0.0 and 1.0"
            )