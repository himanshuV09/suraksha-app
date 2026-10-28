from dataclasses import dataclass

from engine.allocation.artifact_provenance import ArtifactProvenance
from engine.allocation.carved_artifact import CarvedArtifact


@dataclass(frozen=True)
class RecoveredArtifactRecord:
    """
    Immutable forensic record representing a successfully
    recovered artifact together with its cryptographic identity
    and source provenance.
    """

    artifact: CarvedArtifact
    sha256: str
    provenance: ArtifactProvenance

    def __post_init__(self):
        if not isinstance(self.artifact, CarvedArtifact):
            raise TypeError(
                "artifact must be a CarvedArtifact"
            )

        if not isinstance(self.sha256, str):
            raise TypeError(
                "sha256 must be a string"
            )

        if not self.sha256.strip():
            raise ValueError(
                "sha256 cannot be empty"
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

        if not isinstance(
            self.provenance,
            ArtifactProvenance,
        ):
            raise TypeError(
                "provenance must be an ArtifactProvenance"
            )

        if self.artifact.source_offset != self.provenance.source_offset:
            raise ValueError(
                "artifact source_offset must match provenance source_offset"
            )


    @property
    def signature(self):
        return self.artifact.signature

    @property
    def extension(self):
        return self.artifact.extension

    @property
    def size(self):
        return self.artifact.size

    @property
    def confidence(self):
        return self.artifact.confidence

    @property
    def data(self):
        return self.artifact.data