from bisect import bisect_right

from engine.allocation.validated_candidate import ValidatedCandidate
from engine.allocation.extent_analysis import ExtentAnalysis
from engine.volume.geometry import VolumeGeometry


class CandidateExtentAnalyzer:
    """
    Analyzes the filesystem allocation state covered by a
    validated unallocated-space candidate.

    This component does not recover bytes.

    It only determines whether the candidate's byte range
    remains inside unallocated clusters.

    Candidate offsets are absolute image offsets. Allocation ranges use
    volume-relative cluster numbers (LCNs), so ``volume_offset`` (where
    the NTFS volume starts inside the image) is needed to map one onto
    the other.
    """

    def __init__(self, allocation_ranges, cluster_size, volume_offset=0):
        if not isinstance(allocation_ranges, list):
            raise TypeError(
                "allocation_ranges must be a list"
            )

        if not isinstance(cluster_size, int):
            raise TypeError(
                "cluster_size must be an integer"
            )

        if cluster_size <= 0:
            raise ValueError(
                "cluster_size must be positive"
            )

        self.allocation_ranges = sorted(
            allocation_ranges,
            key=lambda item: item["start_cluster"],
        )
        self._range_starts = [
            item["start_cluster"] for item in self.allocation_ranges
        ]
        self.geometry = VolumeGeometry(
            volume_offset=volume_offset,
            cluster_size=cluster_size,
        )

    @property
    def cluster_size(self):
        return self.geometry.cluster_size

    @property
    def volume_offset(self):
        return self.geometry.volume_offset

    def analyze(self, candidate):
        if not isinstance(candidate, ValidatedCandidate):
            raise TypeError(
                "candidate must be a ValidatedCandidate"
            )

        start_offset = candidate.offset
        end_offset = (
            candidate.offset
            + candidate.detected_size
            - 1
        )

        try:
            start_cluster = self.geometry.cluster_at(start_offset)
            end_cluster = self.geometry.cluster_at(end_offset)
        except ValueError as exc:
            # Callers treat LookupError as "not inside known allocation".
            raise LookupError(str(exc)) from exc

        touched_clusters = (
            end_cluster
            - start_cluster
            + 1
        )

        states = [
            self._get_cluster_state(cluster)
            for cluster in range(start_cluster, end_cluster + 1)
        ]

        all_unallocated = all(
            state == "unallocated"
            for state in states
        )

        return ExtentAnalysis(
            start_offset=start_offset,
            end_offset=end_offset,
            start_cluster=start_cluster,
            end_cluster=end_cluster,
            cluster_count=touched_clusters,
            states=states,
            all_unallocated=all_unallocated,
            contiguous=all_unallocated,
        )

    def _get_cluster_state(self, cluster_number):
        index = bisect_right(self._range_starts, cluster_number) - 1

        if index >= 0:
            allocation_range = self.allocation_ranges[index]

            if cluster_number <= allocation_range["end_cluster"]:
                return allocation_range["state"]

        raise LookupError(
            "Cluster does not belong to any allocation range"
        )
