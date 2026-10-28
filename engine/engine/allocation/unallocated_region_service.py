
from engine.allocation.allocation_models import UnallocatedRegion


class UnallocatedRegionService:
    """
    Read-only access to validated NTFS unallocated-space regions.

    This service does not carve files, detect signatures, create
    evidence objects, or modify the forensic image.
    """

    DEFAULT_MAX_READ_SIZE = 64 * 1024

    def __init__(
        self,
        image,
        regions,
        cluster_size,
        max_read_size=DEFAULT_MAX_READ_SIZE,
    ):
        if not isinstance(regions, list):
            raise TypeError("regions must be a list")

        if any(
            not isinstance(region, UnallocatedRegion)
            for region in regions
        ):
            raise TypeError(
                "regions must contain only UnallocatedRegion objects"
            )

        if (
            isinstance(cluster_size, bool)
            or not isinstance(cluster_size, int)
            or cluster_size <= 0
        ):
            raise ValueError("cluster_size must be a positive integer")

        if (
            isinstance(max_read_size, bool)
            or not isinstance(max_read_size, int)
            or max_read_size <= 0
        ):
            raise ValueError("max_read_size must be a positive integer")

        self.image = image
        self.regions = list(regions)
        self.cluster_size = cluster_size
        self.max_read_size = max_read_size

    def list_regions(self):
        """Return a copy of the region list."""
        return list(self.regions)

    def list_region_metadata(self):
        """Return JSON-serializable metadata for every region."""
        return [
            {
                "region_id": index,
                "state": str(
                    getattr(region.state, "value", region.state)
                ),
                "start_cluster": region.start_cluster,
                "end_cluster": region.end_cluster,
                "cluster_count": region.cluster_count,
                "start_offset": region.start_offset,
                "end_offset": region.end_offset,
                "byte_count": region.byte_count,
            }
            for index, region in enumerate(self.regions)
        ]

    def get_region(self, index):
        """Return one region by zero-based index."""
        if isinstance(index, bool) or not isinstance(index, int):
            raise TypeError("index must be an integer")

        if index < 0 or index >= len(self.regions):
            raise IndexError(
                f"Unallocated region index out of range: {index}"
            )

        return self.regions[index]

    def read_region(self, index, relative_offset=0, size=4096):
        """
        Read a bounded byte window relative to a region's beginning.

        Returns raw bytes. The caller can format them as hex and ASCII.
        """
        if (
            isinstance(relative_offset, bool)
            or not isinstance(relative_offset, int)
        ):
            raise TypeError("relative_offset must be an integer")

        if isinstance(size, bool) or not isinstance(size, int):
            raise TypeError("size must be an integer")

        if relative_offset < 0:
            raise ValueError("relative_offset cannot be negative")

        if size <= 0:
            raise ValueError("size must be greater than zero")

        if size > self.max_read_size:
            raise ValueError(
                f"Read exceeds maximum size of {self.max_read_size} bytes"
            )

        region = self.get_region(index)

        if relative_offset >= region.byte_count:
            raise ValueError("relative_offset is outside the region")

        if relative_offset + size > region.byte_count:
            raise ValueError(
                "requested read exceeds the unallocated region"
            )

        absolute_offset = region.start_offset + relative_offset
        absolute_end = absolute_offset + size

        if (
            absolute_offset < region.start_offset
            or absolute_end > region.end_offset
            or absolute_end - absolute_offset != size
        ):
            raise ValueError("Requested read exceeds region bounds")

        # Validate against the actual image length and preserve the
        # shared image cursor, even when a read fails.
        original_position = self.image.tell()

        try:
            self.image.seek(0, 2)
            image_size = self.image.tell()

            if absolute_end > image_size:
                raise IOError("Requested read exceeds image bounds")

            self.image.seek(absolute_offset)
            data = self.image.read(size)

            if len(data) != size:
                raise IOError(
                    "Unable to completely read requested region data"
                )

            return data
        finally:
            self.image.seek(original_position)
