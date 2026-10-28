from dataclasses import dataclass


def _require_int(name, value, minimum):
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be an integer")
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")


@dataclass(frozen=True)
class VolumeGeometry:
    """Where an NTFS volume sits inside a disk image, and its cluster size.

    NTFS stores locations as cluster numbers (LCNs) counted from the start
    of the *volume*. A disk image with a partition table puts the volume at
    some byte offset inside the image, so every LCN must be shifted by
    ``volume_offset`` before it can be used to read the image file.

    All conversions between LCNs and image byte offsets go through this
    class so that the shift is never forgotten.
    """

    volume_offset: int
    cluster_size: int
    total_clusters: int | None = None

    def __post_init__(self):
        _require_int("volume_offset", self.volume_offset, 0)
        _require_int("cluster_size", self.cluster_size, 1)
        if self.total_clusters is not None:
            _require_int("total_clusters", self.total_clusters, 0)

    def cluster_offset(self, lcn):
        """Absolute image offset of the first byte of cluster ``lcn``."""
        _require_int("lcn", lcn, 0)
        return self.volume_offset + lcn * self.cluster_size

    def cluster_at(self, absolute_offset):
        """LCN of the cluster that contains an absolute image offset."""
        _require_int("absolute_offset", absolute_offset, 0)

        if absolute_offset < self.volume_offset:
            raise ValueError(
                f"Offset {absolute_offset} is before the NTFS volume, "
                f"which starts at {self.volume_offset}"
            )

        lcn = (absolute_offset - self.volume_offset) // self.cluster_size

        if self.total_clusters is not None and lcn >= self.total_clusters:
            raise ValueError(
                f"Offset {absolute_offset} is past the end of the NTFS volume"
            )

        return lcn
