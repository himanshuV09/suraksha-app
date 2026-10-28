from engine.allocation.carving_models import SignatureCandidate
from engine.allocation.candidate_region_resolver import (
    CandidateRegionResolver,
)
from engine.allocation.unallocated_candidate_context import (
    UnallocatedCandidateContext,
)


class CandidateContextFactory:
    """
    Creates a safe UnallocatedCandidateContext.

    The factory enforces the relationship:

        SignatureCandidate
                ↓
        CandidateRegionResolver
                ↓
        UnallocatedRegion
                ↓
        UnallocatedCandidateContext

    A caller does not supply the region directly.

    This prevents a candidate from being bound to an
    arbitrary or incorrect unallocated region.

    This component does NOT:

        - validate file structure
        - determine file size
        - carve files
        - modify the forensic image
        - create evidence objects
    """

    def __init__(
        self,
        image,
        regions,
    ):
        if image is None:
            raise ValueError(
                "image cannot be None"
            )

        self.image = image

        self.resolver = CandidateRegionResolver(
            regions
        )

    def create(
        self,
        candidate,
    ):
        """
        Resolve the candidate's containing region and
        create a bounded candidate context.

        Returns:
            UnallocatedCandidateContext

        Raises:
            TypeError
                If candidate is not a SignatureCandidate.

            LookupError
                If the candidate does not belong to
                any unallocated region.

            ValueError
                If candidate provenance conflicts
                with the containing region.
        """

        if not isinstance(
            candidate,
            SignatureCandidate,
        ):
            raise TypeError(
                "candidate must be a SignatureCandidate"
            )

        region = self.resolver.resolve(
            candidate
        )

        return UnallocatedCandidateContext(
            image=self.image,
            region=region,
            candidate=candidate,
        )