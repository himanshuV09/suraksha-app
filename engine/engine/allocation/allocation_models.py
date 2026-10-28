
from dataclasses import dataclass


@dataclass(frozen=True)
class UnallocatedRegion:
    """
    A contiguous region of clusters marked unallocated by the NTFS bitmap.

    Cluster bounds are inclusive.
    Byte offsets use a half-open interval: [start_offset, end_offset).

    This represents allocation state only; it does not imply that
    deleted files or recoverable content exist in the region.
    """

    start_cluster: int
    end_cluster: int
    cluster_count: int

    start_offset: int
    end_offset: int
    byte_count: int

    state: str = "UNALLOCATED"

    def __post_init__(self):
        integer_fields = (
            "start_cluster",
            "end_cluster",
            "cluster_count",
            "start_offset",
            "end_offset",
            "byte_count",
        )

        for field_name in integer_fields:
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool):
                raise TypeError(f"{field_name} must be an integer")

        if self.start_cluster < 0:
            raise ValueError("start_cluster cannot be negative")

        if self.end_cluster < self.start_cluster:
            raise ValueError(
                "end_cluster cannot be less than start_cluster"
            )

        expected_cluster_count = (
            self.end_cluster - self.start_cluster + 1
        )
        if self.cluster_count != expected_cluster_count:
            raise ValueError(
                "cluster_count does not match cluster bounds"
            )

        if self.start_offset < 0:
            raise ValueError("start_offset cannot be negative")

        if self.end_offset <= self.start_offset:
            raise ValueError(
                "end_offset must be greater than start_offset"
            )

        expected_byte_count = self.end_offset - self.start_offset
        if self.byte_count != expected_byte_count:
            raise ValueError(
                "byte_count must equal end_offset - start_offset"
            )

        if self.state != "UNALLOCATED":
            raise ValueError(
                "UnallocatedRegion state must be 'UNALLOCATED'"
            )
