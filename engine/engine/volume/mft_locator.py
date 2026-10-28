from bisect import bisect_right
from dataclasses import dataclass

from engine.volume.geometry import VolumeGeometry


@dataclass(frozen=True)
class _Extent:
    """One data run of the $MFT stream."""

    stream_start: int       # first byte of this run within the $MFT stream
    stream_end: int         # exclusive
    image_offset: int | None  # None for a sparse run (reads as zeros)


class MftRecordLocator:
    """Finds MFT records by following the $MFT file's own data runs.

    The MFT is stored as an ordinary file ($MFT, record 0). On a volume
    that has grown over time it is split into several runs scattered
    across the disk. Record N lives at byte ``N * record_size`` of the
    *$MFT stream*, which can be in any of those runs, so it cannot be
    found by adding ``N * record_size`` to the MFT's first cluster.

    A record may also straddle two runs when the record size is larger
    than the cluster size; ``read`` stitches such records together.
    """

    def __init__(self, data_runs, geometry, record_size, mft_size):
        if not isinstance(geometry, VolumeGeometry):
            raise TypeError("geometry must be a VolumeGeometry")
        if not isinstance(record_size, int) or record_size <= 0:
            raise ValueError("record_size must be a positive integer")
        if not isinstance(mft_size, int) or mft_size <= 0:
            raise ValueError("mft_size must be a positive integer")
        if not data_runs:
            raise ValueError("$MFT has no data runs")

        self.geometry = geometry
        self.record_size = record_size
        self.mft_size = mft_size
        self.extents = self._build_extents(data_runs)
        self._extent_starts = [extent.stream_start for extent in self.extents]

    def _build_extents(self, data_runs):
        extents = []
        position = 0

        for run in data_runs:
            length = run["length"] * self.geometry.cluster_size
            if length <= 0:
                raise ValueError("$MFT data run has a non-positive length")

            image_offset = (
                None
                if run.get("sparse")
                else self.geometry.cluster_offset(run["lcn"])
            )
            extents.append(
                _Extent(position, position + length, image_offset)
            )
            position += length

        return extents

    @property
    def mapped_bytes(self):
        """How many bytes of the $MFT stream the data runs describe."""
        return self.extents[-1].stream_end

    @property
    def record_count(self):
        """Number of records that are both in use by $MFT and mapped."""
        return min(self.mft_size, self.mapped_bytes) // self.record_size

    @property
    def is_fragmented(self):
        return len(self.extents) > 1

    def record_offset(self, record_number):
        """Image offset of a record's first byte, or None if unmapped."""
        stream_offset = record_number * self.record_size
        extent = self._extent_for(stream_offset)
        if extent is None or extent.image_offset is None:
            return None
        return extent.image_offset + (stream_offset - extent.stream_start)

    def read(self, image, record_number):
        """Read one raw record.

        Returns ``b""`` if the record lies outside the mapped stream, and
        fewer than ``record_size`` bytes if the image is truncated.
        """
        if not isinstance(record_number, int) or record_number < 0:
            raise ValueError("record_number must be a non-negative integer")

        start = record_number * self.record_size
        end = start + self.record_size

        if end > self.mapped_bytes:
            return b""

        data = bytearray()
        position = start

        while position < end:
            extent = self._extent_for(position)
            take = min(end, extent.stream_end) - position

            if extent.image_offset is None:
                data.extend(bytes(take))
            else:
                image.seek(
                    extent.image_offset + (position - extent.stream_start)
                )
                chunk = image.read(take)
                data.extend(chunk)
                if len(chunk) < take:
                    break  # truncated image

            position += take

        return bytes(data)

    def _extent_for(self, stream_offset):
        index = bisect_right(self._extent_starts, stream_offset) - 1
        if index < 0:
            return None
        extent = self.extents[index]
        if stream_offset < extent.stream_end:
            return extent
        return None
