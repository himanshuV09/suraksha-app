from engine.allocation.allocation_models import (
    UnallocatedRegion,
)

from engine.allocation.carving_models import (
    SignatureCandidate,
)


class CandidateRegionResolver:
    """
    Resolves a SignatureCandidate to the exact
    UnallocatedRegion containing it.

    Resolution is based on absolute byte offset.

    Candidate cluster metadata is additionally checked
    when present.

    This component does NOT:

        - read image data
        - validate file structure
        - carve files
        - modify the forensic image
        - create evidence records

    The resolver must never guess a region.
    """

    def __init__(self, regions):
        if not isinstance(regions, list):
            raise TypeError(
                "regions must be a list"
            )

        for region in regions:
            if not isinstance(
                region,
                UnallocatedRegion,
            ):
                raise TypeError(
                    "regions must contain only "
                    "UnallocatedRegion objects"
                )

        self.regions = list(regions)

    def resolve(
        self,
        candidate,
    ):
        """
        Resolve a candidate to its containing
        unallocated region.

        Returns:
            UnallocatedRegion

        Raises:
            TypeError
                If candidate is not a SignatureCandidate.

            LookupError
                If no region contains the candidate.

            ValueError
                If multiple regions contain the candidate
                or candidate cluster metadata conflicts
                with the matched region.
        """

        if not isinstance(
            candidate,
            SignatureCandidate,
        ):
            raise TypeError(
                "candidate must be a SignatureCandidate"
            )

        matching_regions = [
            region
            for region in self.regions
            if (
                region.start_offset
                <= candidate.offset
                < region.end_offset
            )
        ]

        if not matching_regions:
            raise LookupError(
                "Candidate offset does not belong "
                "to any unallocated region"
            )

        if len(matching_regions) > 1:
            raise ValueError(
                "Candidate offset matches multiple "
                "unallocated regions"
            )

        region = matching_regions[0]

        if (
            candidate.start_cluster is not None
            and candidate.start_cluster
            != region.start_cluster
        ):
            raise ValueError(
                "Candidate start_cluster does not "
                "match the containing unallocated region"
            )

        if (
            candidate.end_cluster is not None
            and candidate.end_cluster
            != region.end_cluster
        ):
            raise ValueError(
                "Candidate end_cluster does not "
                "match the containing unallocated region"
            )

        return region