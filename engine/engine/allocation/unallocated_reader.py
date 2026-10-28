from engine import progress

from engine.allocation.allocation_models import UnallocatedRegion


class UnallocatedReader:
    """Read validated raw unallocated regions in bounded chunks."""

    def __init__(self, image, ranges, cluster_size, chunk_size=1024 * 1024):
        if not isinstance(ranges, list):
            raise TypeError("ranges must be a list")

        if not isinstance(cluster_size, int) or isinstance(cluster_size, bool) or cluster_size <= 0:
            raise ValueError("cluster_size must be a positive integer")

        if not isinstance(chunk_size, int) or isinstance(chunk_size, bool) or chunk_size <= 0:
            raise ValueError("chunk_size must be a positive integer")

        if not hasattr(image, "seek") or not hasattr(image, "read") or not hasattr(image, "tell"):
            raise TypeError("image must be a seekable binary file")

        for region in ranges:
            if not isinstance(region, UnallocatedRegion):
                raise TypeError("Every range must be an UnallocatedRegion")

            if region.start_cluster < 0 or region.end_cluster < region.start_cluster:
                raise ValueError("Invalid cluster bounds")

            if region.cluster_count != region.end_cluster - region.start_cluster + 1:
                raise ValueError("Invalid cluster count")

            if region.start_offset < 0:
                raise ValueError("Negative region offset")

            if region.end_offset <= region.start_offset:
                raise ValueError("Invalid half-open byte range")

            if region.byte_count != region.end_offset - region.start_offset:
                raise ValueError("Region byte count does not match its offsets")

            if region.byte_count != region.cluster_count * cluster_size:
                raise ValueError("Region byte count does not match cluster geometry")

            state = str(getattr(region.state, "value", region.state)).upper()
            if state != "UNALLOCATED":
                raise ValueError("Reader only accepts unallocated regions")

        self.image = image
        self.ranges = ranges
        self.cluster_size = cluster_size
        self.chunk_size = chunk_size

    def iter_chunks(self):
        """Yield raw bytes and absolute offsets without loading whole regions."""

        original_position = self.image.tell()

        try:
            self.image.seek(0, 2)
            image_size = self.image.tell()

            total = sum(region.byte_count for region in self.ranges)
            scanned = 0

            for region in self.ranges:
                if region.end_offset > image_size:
                    raise IOError("Unallocated region exceeds image bounds")

                position = 0

                while position < region.byte_count:
                    read_size = min(
                        self.chunk_size,
                        region.byte_count - position,
                    )
                    offset = region.start_offset + position

                    self.image.seek(offset)
                    data = self.image.read(read_size)

                    if len(data) != read_size:
                        raise IOError(
                            f"Short read at offset {offset}: "
                            f"expected {read_size}, received {len(data)}"
                        )

                    chunk_start_cluster = (
                        region.start_cluster + position // self.cluster_size
                    )
                    chunk_end_cluster = (
                        region.start_cluster
                        + (position + read_size - 1) // self.cluster_size
                    )

                    yield {
                        "data": data,
                        "offset": offset,
                        "start_cluster": chunk_start_cluster,
                        "end_cluster": chunk_end_cluster,
                        "size": len(data),
                    }

                    position += read_size
                    scanned += read_size
                    progress.report("Scanning free space", scanned, total)

        finally:
            self.image.seek(original_position)
