from engine.allocation.carved_artifact import CarvedArtifact
from engine.allocation.carver import Carver
from engine.allocation.candidate_extent_analyzer import (
    CandidateExtentAnalyzer,
)
from engine.allocation.extent_analysis import ExtentAnalysis
from engine.allocation.fragment_analyzer import FragmentAnalyzer
from engine.allocation.recovery_planner import RecoveryPlanner
from engine.allocation.recovery_plan import RecoveryPlan
from engine.allocation.validated_candidate import (
    ValidatedCandidate,
)

from engine.allocation.recovery_result import (
    RecoveryResult,
    RecoveryStatus,
)


class UnallocatedCarvingService:
    """
    Orchestrates recovery of validated candidates from
    unallocated filesystem space.

    Current MVP behavior:

        ValidatedCandidate
            ↓
        CandidateExtentAnalyzer
            ↓
        ExtentAnalysis
            ↓
        FragmentAnalyzer
            ↓
        RecoveryPlanner
            ↓
        RecoveryPlan
            ↓
        Carver
            ↓
        CarvedArtifact

    The service only permits candidates whose complete
    extent remains inside unallocated space.

    It does not:
        - detect signatures
        - validate signatures
        - analyze filesystem allocation
        - write recovered files
        - create database records
        - calculate hashes
        - implement UI behavior
    """

    def __init__(
        self,
        extent_analyzer,
        fragment_analyzer,
        recovery_planner,
        carver,
    ):
        if not isinstance(
            extent_analyzer,
            CandidateExtentAnalyzer,
        ):
            raise TypeError(
                "extent_analyzer must be a CandidateExtentAnalyzer"
            )

        if not isinstance(
            fragment_analyzer,
            FragmentAnalyzer,
        ):
            raise TypeError(
                "fragment_analyzer must be a FragmentAnalyzer"
            )

        if not isinstance(
            recovery_planner,
            RecoveryPlanner,
        ):
            raise TypeError(
                "recovery_planner must be a RecoveryPlanner"
            )

        if not isinstance(
            carver,
            Carver,
        ):
            raise TypeError(
                "carver must be a Carver"
            )

        self.extent_analyzer = extent_analyzer
        self.fragment_analyzer = fragment_analyzer
        self.recovery_planner = recovery_planner
        self.carver = carver

    def recover(self, candidate):
        """
        Recover one validated candidate.

        Returns:
            RecoveryResult
        """

        if not isinstance(
            candidate,
            ValidatedCandidate,
        ):
            raise TypeError(
                "candidate must be a ValidatedCandidate"
            )

        try:
            extent_analysis = self.extent_analyzer.analyze(candidate)
        except LookupError as exc:
            return RecoveryResult(
                status=RecoveryStatus.ALLOCATED_CROSSING,
                reason=(
                    "Candidate extent falls outside known allocation "
                    f"ranges: {exc}"
                ),
            )

        if not isinstance(
            extent_analysis,
            ExtentAnalysis,
        ):
            raise TypeError(
                "extent_analyzer returned an invalid "
                "ExtentAnalysis"
            )

        fragment_analysis = (
            self.fragment_analyzer.analyze(
                extent_analysis
            )
        )

        if not fragment_analysis.complete:
            if not extent_analysis.all_unallocated:
                return RecoveryResult(
                    status=RecoveryStatus.ALLOCATED_CROSSING,
                    reason=(
                        "Candidate extent crosses allocated "
                        "filesystem space"
                    ),
                )

            return RecoveryResult(
                status=RecoveryStatus.FRAGMENTED_UNSUPPORTED,
                reason=(
                    "Candidate extent is fragmented and "
                    "fragmented recovery is not supported"
                ),
            )

        try:
            recovery_plan = (
                self.recovery_planner.create_plan(
                    candidate,
                    extent_analysis,
                )
            )
        except ValueError as exc:
            return RecoveryResult(
                status=RecoveryStatus.RECOVERY_FAILED,
                reason=str(exc),
            )

        if not isinstance(
            recovery_plan,
            RecoveryPlan,
        ):
            raise TypeError(
                "recovery_planner returned an invalid "
                "RecoveryPlan"
            )

        try:
            artifact = self.carver.carve(
                recovery_plan
            )
        except Exception as exc:
            return RecoveryResult(
                status=RecoveryStatus.RECOVERY_FAILED,
                reason=str(exc),
            )

        if not isinstance(
            artifact,
            CarvedArtifact,
        ):
            raise TypeError(
                "carver returned an invalid "
                "CarvedArtifact"
            )

        return RecoveryResult(
            status=RecoveryStatus.RECOVERED,
            artifact=artifact,
            reason="Candidate recovered successfully",
        )

    def recover_many(self, candidates):
        """
        Recover multiple validated candidates.

        Candidates that cannot safely be recovered are skipped.

        Returns:
            list[RecoveryResult], one result per supplied candidate
        """

        if not isinstance(
            candidates,
            list,
        ):
            raise TypeError(
                "candidates must be a list"
            )

        for candidate in candidates:
            if not isinstance(
                candidate,
                ValidatedCandidate,
            ):
                raise TypeError(
                    "candidates must contain only "
                    "ValidatedCandidate objects"
                )

        artifacts = []

        for candidate in candidates:
            try:
                artifact = self.recover(
                    candidate
                )
            except ValueError:
                continue

            artifacts.append(artifact)

        return artifacts