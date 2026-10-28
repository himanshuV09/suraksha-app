from dataclasses import dataclass


@dataclass(frozen=True)
class ExtentAnalysis:
    """
    Describes the allocation state covered by a validated
    unallocated-space candidate.

    This is an analysis result only.

    It does NOT:
        - recover data
        - create a RecoveryPlan
        - carve bytes
        - write files
    """

    start_offset: int
    end_offset: int
    start_cluster: int
    end_cluster: int
    cluster_count: int
    states: list
    all_unallocated: bool
    contiguous: bool

    def __post_init__(self):
        if self.start_offset < 0:
            raise ValueError(
                "start_offset cannot be negative"
            )

        if self.end_offset < self.start_offset:
            raise ValueError(
                "end_offset cannot be less than start_offset"
            )

        if self.start_cluster < 0:
            raise ValueError(
                "start_cluster cannot be negative"
            )

        if self.end_cluster < self.start_cluster:
            raise ValueError(
                "end_cluster cannot be less than start_cluster"
            )

        expected_cluster_count = (
            self.end_cluster
            - self.start_cluster
            + 1
        )

        if self.cluster_count != expected_cluster_count:
            raise ValueError(
                "cluster_count does not match "
                "start_cluster/end_cluster"
            )

        if not isinstance(self.states, list):
            raise TypeError(
                "states must be a list"
            )

        if len(self.states) != self.cluster_count:
            raise ValueError(
                "states length must match cluster_count"
            )

        if not isinstance(self.all_unallocated, bool):
            raise TypeError(
                "all_unallocated must be a boolean"
            )

        if not isinstance(self.contiguous, bool):
            raise TypeError(
                "contiguous must be a boolean"
            )

        if self.all_unallocated != all(
            state == "unallocated"
            for state in self.states
        ):
            raise ValueError(
                "all_unallocated does not match states"
            )

        if self.contiguous != self.all_unallocated:
            raise ValueError(
                "contiguous must match all_unallocated"
            )