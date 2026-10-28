import hashlib
from dataclasses import dataclass

from engine.allocation.artifact_hasher import ArtifactHasher
from engine.allocation.artifact_provenance_factory import ArtifactProvenanceFactory
from engine.allocation.carved_artifact import CarvedArtifact
from engine.allocation.recovered_artifact_assembler import RecoveredArtifactAssembler
from engine.allocation.recovery_result import RecoveryResult, RecoveryStatus
from engine.allocation.unallocated_candidate_context import UnallocatedCandidateContext
from engine.allocation.allocation_models import UnallocatedRegion
from engine.allocation.validated_candidate import ValidatedCandidate


@dataclass(frozen=True)
class UnallocatedRecoveryResult:
    recovery: RecoveryResult
    artifact: CarvedArtifact | None
    sha256: str | None
    source_image: str
    source_type: str
    region_start_cluster: int
    region_end_cluster: int
    region_start_offset: int
    relative_offset: int
    artifact_id: int | None = None


class UnallocatedRecoveryWorkflow:
    """Coordinate safe carving, provenance assembly, and persistence."""

    def __init__(self, recovery_service, assembler=None):
        if recovery_service is None:
            raise ValueError("recovery_service cannot be None")
        if not callable(getattr(recovery_service, "recover", None)):
            raise TypeError("recovery_service must provide recover()")

        if assembler is not None and not isinstance(assembler, RecoveredArtifactAssembler):
            raise TypeError("assembler must be a RecoveredArtifactAssembler")

        self.recovery_service = recovery_service
        self.assembler = assembler or RecoveredArtifactAssembler(
            artifact_hasher=ArtifactHasher(),
            provenance_factory=ArtifactProvenanceFactory(),
        )

    @staticmethod
    def _validate_inputs(image, region, candidate, source_image):
        if not isinstance(source_image, str):
            raise TypeError("source_image must be a string")
        if not source_image.strip():
            raise ValueError("source_image cannot be empty")
        if image is None:
            raise ValueError("image cannot be None")
        if not isinstance(region, UnallocatedRegion):
            raise TypeError("region must be an UnallocatedRegion")
        if not isinstance(candidate, ValidatedCandidate):
            raise TypeError("candidate must be a ValidatedCandidate")

        # region.end_offset is exclusive: the region covers
        # [start_offset, end_offset).
        if candidate.offset < region.start_offset:
            raise ValueError("candidate offset is before the unallocated region")
        if candidate.offset >= region.end_offset:
            raise ValueError("candidate offset is outside the unallocated region")

        candidate_end = candidate.offset + candidate.detected_size - 1
        if candidate_end >= region.end_offset:
            raise ValueError(
                "candidate extent exceeds the containing unallocated region"
            )

    def recover(self, image, region, candidate, source_image) -> UnallocatedRecoveryResult:
        self._validate_inputs(image, region, candidate, source_image)

        recovery = self.recovery_service.recover(candidate)
        if not isinstance(recovery, RecoveryResult):
            raise TypeError(
                "recovery_service.recover() must return a RecoveryResult"
            )

        relative_offset = candidate.offset - region.start_offset
        if recovery.status != RecoveryStatus.RECOVERED:
            return UnallocatedRecoveryResult(
                recovery=recovery,
                artifact=None,
                sha256=None,
                source_image=source_image,
                source_type="UNALLOCATED",
                region_start_cluster=region.start_cluster,
                region_end_cluster=region.end_cluster,
                region_start_offset=region.start_offset,
                relative_offset=relative_offset,
            )

        artifact = recovery.artifact
        if not isinstance(artifact, CarvedArtifact):
            raise TypeError("RECOVERED result must contain a CarvedArtifact")

        artifact_end = artifact.source_offset + artifact.size - 1
        if artifact.source_offset < region.start_offset or artifact_end >= region.end_offset:
            raise ValueError(
                "complete artifact extent must remain inside the unallocated region"
            )

        sha256 = hashlib.sha256(artifact.data).hexdigest()
        return UnallocatedRecoveryResult(
            recovery=recovery,
            artifact=artifact,
            sha256=sha256,
            source_image=source_image,
            source_type="UNALLOCATED",
            region_start_cluster=region.start_cluster,
            region_end_cluster=region.end_cluster,
            region_start_offset=region.start_offset,
            relative_offset=artifact.source_offset - region.start_offset,
        )

    def recover_and_persist(
        self,
        image,
        region,
        candidate,
        source_image,
        case_id,
        repository,
    ) -> UnallocatedRecoveryResult:
        # Keep validation order stable so callers receive useful errors early.
        if repository is None:
            raise ValueError("repository cannot be None")
        if not isinstance(case_id, int) or isinstance(case_id, bool):
            raise TypeError("case_id must be an integer")
        if case_id <= 0:
            raise ValueError("case_id must be greater than zero")
        self._validate_inputs(image, region, candidate, source_image)

        result = self.recover(
            image=image,
            region=region,
            candidate=candidate,
            source_image=source_image,
        )
        if result.recovery.status != RecoveryStatus.RECOVERED:
            return result

        extent_analyzer = getattr(self.recovery_service, "extent_analyzer", None)
        if not callable(getattr(extent_analyzer, "analyze", None)):
            raise TypeError(
                "recovery_service must expose extent_analyzer.analyze() "
                "to assemble provenance"
            )

        extent_analysis = extent_analyzer.analyze(candidate)
        context = UnallocatedCandidateContext(
            image=image,
            region=region,
            candidate=candidate.candidate,
        )
        record = self.assembler.assemble(
            artifact=result.artifact,
            context=context,
            extent_analysis=extent_analysis,
            source_image=source_image,
        )
        artifact_id = repository.create(case_id, record)
        if not isinstance(artifact_id, int) or isinstance(artifact_id, bool) or artifact_id <= 0:
            raise ValueError("repository.create() must return a positive artifact ID")

        return UnallocatedRecoveryResult(
            recovery=result.recovery,
            artifact=result.artifact,
            sha256=record.sha256,
            source_image=result.source_image,
            source_type=result.source_type,
            region_start_cluster=result.region_start_cluster,
            region_end_cluster=result.region_end_cluster,
            region_start_offset=result.region_start_offset,
            relative_offset=result.relative_offset,
            artifact_id=artifact_id,
        )
