from engine.allocation.artifact_hasher import ArtifactHasher
from engine.allocation.artifact_provenance_factory import (
    ArtifactProvenanceFactory,
)
from engine.allocation.carved_artifact import CarvedArtifact
from engine.allocation.extent_analysis import ExtentAnalysis
from engine.allocation.recovered_artifact_record import (
    RecoveredArtifactRecord,
)
from engine.allocation.unallocated_candidate_context import (
    UnallocatedCandidateContext,
)


class RecoveredArtifactAssembler:
    """
    Assembles a recovered carved artifact into an immutable
    forensic evidence record.

    Responsibility:

        CarvedArtifact
                +
        ExtentAnalysis
                +
        UnallocatedCandidateContext
                +
        source image
                ↓
        SHA-256
                +
        provenance
                ↓
        RecoveredArtifactRecord

    This component does not:

        - detect signatures
        - validate signatures
        - analyze filesystem allocation
        - perform carving
        - write recovered files
        - persist database records
        - modify the forensic image
    """

    def __init__(
        self,
        artifact_hasher,
        provenance_factory,
    ):
        if not isinstance(
            artifact_hasher,
            ArtifactHasher,
        ):
            raise TypeError(
                "artifact_hasher must be an ArtifactHasher"
            )

        if not isinstance(
            provenance_factory,
            ArtifactProvenanceFactory,
        ):
            raise TypeError(
                "provenance_factory must be an "
                "ArtifactProvenanceFactory"
            )

        self.artifact_hasher = artifact_hasher
        self.provenance_factory = provenance_factory

    def assemble(
        self,
        artifact,
        context,
        extent_analysis,
        source_image,
    ):
        """
        Assemble a CarvedArtifact into a
        RecoveredArtifactRecord.
        """

        if not isinstance(
            artifact,
            CarvedArtifact,
        ):
            raise TypeError(
                "artifact must be a CarvedArtifact"
            )

        if not isinstance(
            context,
            UnallocatedCandidateContext,
        ):
            raise TypeError(
                "context must be an "
                "UnallocatedCandidateContext"
            )

        if not isinstance(
            extent_analysis,
            ExtentAnalysis,
        ):
            raise TypeError(
                "extent_analysis must be an "
                "ExtentAnalysis"
            )

        if not isinstance(
            source_image,
            str,
        ):
            raise TypeError(
                "source_image must be a string"
            )

        if not source_image.strip():
            raise ValueError(
                "source_image cannot be empty"
            )

        if (
            extent_analysis.start_offset
            != artifact.source_offset
        ):
            raise ValueError(
                "extent start offset must match "
                "artifact source offset"
            )

        if (
            artifact.source_offset
            != context.absolute_offset
        ):
            raise ValueError(
                "artifact source offset must match "
                "candidate absolute offset"
            )

        sha256 = self.artifact_hasher.sha256(
            artifact
        )

        provenance = self.provenance_factory.create(
            context=context,
            extent_analysis=extent_analysis,
            source_image=source_image,
        )

        return RecoveredArtifactRecord(
            artifact=artifact,
            sha256=sha256,
            provenance=provenance,
        )