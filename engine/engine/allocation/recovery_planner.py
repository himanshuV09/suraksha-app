from engine.allocation.extent_analysis import ExtentAnalysis
from engine.allocation.recovery_plan import RecoveryPlan
from engine.allocation.validated_candidate import ValidatedCandidate


class RecoveryPlanner:
    """
    Creates a RecoveryPlan only when a validated candidate's
    complete extent remains inside unallocated space.

    This component does not:
        - read image data
        - carve bytes
        - write recovered files
        - create evidence objects
    """

    def create_plan(
        self,
        candidate,
        extent_analysis,
    ):
        if not isinstance(candidate, ValidatedCandidate):
            raise TypeError(
                "candidate must be a ValidatedCandidate"
            )

        if not isinstance(extent_analysis, ExtentAnalysis):
            raise TypeError(
                "extent_analysis must be an ExtentAnalysis"
            )

        if extent_analysis.start_offset != candidate.offset:
            raise ValueError(
                "Extent analysis start offset does not match candidate"
            )

        expected_end_offset = (
            candidate.offset
            + candidate.detected_size
            - 1
        )

        if extent_analysis.end_offset != expected_end_offset:
            raise ValueError(
                "Extent analysis end offset does not match candidate"
            )

        if not extent_analysis.all_unallocated:
            raise ValueError(
                "Candidate extent crosses allocated space"
            )

        if not extent_analysis.contiguous:
            raise ValueError(
                "Candidate extent is not contiguous"
            )

        return RecoveryPlan(
            candidate=candidate,
            source_offset=candidate.offset,
            requested_size=candidate.detected_size,
            contiguous=True,
        )