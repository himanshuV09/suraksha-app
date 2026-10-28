from engine.allocation.artifact_provenance import (
    ArtifactProvenance,
)
from engine.allocation.extent_analysis import ExtentAnalysis
from engine.allocation.unallocated_candidate_context import (
    UnallocatedCandidateContext,
)


class ArtifactProvenanceFactory:
    """
    Creates immutable forensic provenance from an
    unallocated candidate context and its analyzed extent.

    This component does not:
        - read image data
        - validate signatures
        - carve artifacts
        - calculate hashes
        - persist evidence
    """

    def create(
        self,
        context,
        extent_analysis,
        source_image,
    ):
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
            != context.absolute_offset
        ):
            raise ValueError(
                "extent start offset must match "
                "candidate absolute offset"
            )

        provenance = ArtifactProvenance(
            source_image=source_image,
            source_type="UNALLOCATED",
            region_start_cluster=(
                context.region.start_cluster
            ),
            region_end_cluster=(
                context.region.end_cluster
            ),
            region_start_offset=(
                context.region.start_offset
            ),
            source_offset=(
                context.absolute_offset
            ),
            relative_offset=(
                context.relative_offset
            ),
            start_cluster=(
                extent_analysis.start_cluster
            ),
            end_cluster=(
                extent_analysis.end_cluster
            ),
        )

        return provenance