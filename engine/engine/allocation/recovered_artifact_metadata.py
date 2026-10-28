from dataclasses import dataclass


@dataclass(frozen=True)
class RecoveredArtifactMetadata:
    """
    Immutable persisted metadata describing a recovered artifact.

    This model contains forensic identity, source provenance,
    recovery size, validation information, and cryptographic identity.

    It intentionally does NOT contain recovered file bytes.

    The original forensic image remains the authoritative source
    for the recovered data.
    """

    artifact_id: int

    signature: str
    extension: str
    size: int
    sha256: str
    confidence: float

    source_image: str
    source_type: str

    region_start_cluster: int
    region_end_cluster: int
    region_start_offset: int

    source_offset: int
    relative_offset: int

    start_cluster: int
    end_cluster: int

    validation_reason: str

    # For files reassembled from several free-space pieces: the
    # [absolute_offset, length] of each piece, in order. None when the
    # file is one contiguous run starting at source_offset.
    fragments: list | None = None

    def __post_init__(self):

        if not isinstance(self.artifact_id, int):
            raise TypeError(
                "artifact_id must be an integer"
            )

        if self.artifact_id <= 0:
            raise ValueError(
                "artifact_id must be greater than zero"
            )

        if not isinstance(self.signature, str):
            raise TypeError(
                "signature must be a string"
            )

        if not self.signature.strip():
            raise ValueError(
                "signature cannot be empty"
            )

        if not isinstance(self.extension, str):
            raise TypeError(
                "extension must be a string"
            )

        if not self.extension.strip():
            raise ValueError(
                "extension cannot be empty"
            )

        if not isinstance(self.size, int):
            raise TypeError(
                "size must be an integer"
            )

        if self.size <= 0:
            raise ValueError(
                "size must be greater than zero"
            )

        if not isinstance(self.sha256, str):
            raise TypeError(
                "sha256 must be a string"
            )

        normalized_hash = self.sha256.lower()

        if len(normalized_hash) != 64:
            raise ValueError(
                "sha256 must contain exactly 64 hexadecimal characters"
            )

        if any(
            character not in "0123456789abcdef"
            for character in normalized_hash
        ):
            raise ValueError(
                "sha256 must contain only hexadecimal characters"
            )

        if not isinstance(self.confidence, (int, float)):
            raise TypeError(
                "confidence must be a number"
            )

        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                "confidence must be between 0.0 and 1.0"
            )

        if not isinstance(self.source_image, str):
            raise TypeError(
                "source_image must be a string"
            )

        if not self.source_image.strip():
            raise ValueError(
                "source_image cannot be empty"
            )

        if not isinstance(self.source_type, str):
            raise TypeError(
                "source_type must be a string"
            )

        if not self.source_type.strip():
            raise ValueError(
                "source_type cannot be empty"
            )

        integer_fields = (
            "region_start_cluster",
            "region_end_cluster",
            "region_start_offset",
            "source_offset",
            "relative_offset",
            "start_cluster",
            "end_cluster",
        )

        for field_name in integer_fields:

            value = getattr(self, field_name)

            if not isinstance(value, int):
                raise TypeError(
                    f"{field_name} must be an integer"
                )

            if value < 0:
                raise ValueError(
                    f"{field_name} cannot be negative"
                )

        if self.region_start_cluster > self.region_end_cluster:
            raise ValueError(
                "region_start_cluster cannot exceed "
                "region_end_cluster"
            )

        if self.start_cluster > self.end_cluster:
            raise ValueError(
                "start_cluster cannot exceed end_cluster"
            )

        if self.source_offset < self.region_start_offset:
            raise ValueError(
                "source_offset cannot be before "
                "region_start_offset"
            )

        expected_relative_offset = (
            self.source_offset
            - self.region_start_offset
        )

        if self.relative_offset != expected_relative_offset:
            raise ValueError(
                "relative_offset must equal "
                "source_offset - region_start_offset"
            )

        if self.start_cluster < self.region_start_cluster:
            raise ValueError(
                "start_cluster cannot be before "
                "region_start_cluster"
            )

        if self.end_cluster > self.region_end_cluster:
            raise ValueError(
                "end_cluster cannot exceed "
                "region_end_cluster"
            )

        if not isinstance(self.validation_reason, str):
            raise TypeError(
                "validation_reason must be a string"
            )

        if not self.validation_reason.strip():
            raise ValueError(
                "validation_reason cannot be empty"
            )