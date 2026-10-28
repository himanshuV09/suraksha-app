"""Read free space as one stream that skips allocated clusters.

When NTFS writes a file into free space and meets clusters already in
use, it continues in the next free clusters. A deleted file that was
fragmented that way therefore continues right after the allocated block
that interrupted it. Reading free space with allocated clusters skipped
("carving the unallocated stream", as done on extracted unallocated
space by tools like foremost/scalpel) puts its pieces back together.

The stream offers the same ``read(size, relative_offset=)`` and
``remaining_bytes`` interface as UnallocatedCandidateContext, so the
format validators work on it unchanged.
"""
from bisect import bisect_right


class FreeSpaceStream:

    def __init__(self, image, regions, start_offset, candidate):
        """Free bytes from ``start_offset`` (absolute) to the volume's end."""
        self.image = image
        self.candidate = candidate
        self.extents = []  # (stream_start, image_offset, length)
        position = 0
        for region in sorted(regions, key=lambda item: item.start_offset):
            if region.end_offset <= start_offset:
                continue
            begin = max(region.start_offset, start_offset)
            length = region.end_offset - begin
            self.extents.append((position, begin, length))
            position += length
        if not self.extents or self.extents[0][1] != start_offset:
            raise LookupError("start offset is not inside free space")
        self._starts = [extent[0] for extent in self.extents]
        self.remaining_bytes = position

    def read(self, size, relative_offset=0):
        end = min(relative_offset + size, self.remaining_bytes)
        data = bytearray()
        position = relative_offset
        index = max(0, bisect_right(self._starts, position) - 1)
        while position < end and index < len(self.extents):
            stream_start, image_offset, length = self.extents[index]
            if position >= stream_start + length:
                index += 1
                continue
            take = min(end, stream_start + length) - position
            self.image.seek(image_offset + position - stream_start)
            chunk = self.image.read(take)
            data += chunk
            if len(chunk) < take:
                break
            position += take
            index += 1
        return bytes(data)

    def fragments(self, size):
        """[(absolute_offset, length), ...] holding the first ``size`` bytes."""
        pieces = []
        remaining = size
        for _, image_offset, length in self.extents:
            if remaining <= 0:
                break
            take = min(length, remaining)
            pieces.append((image_offset, take))
            remaining -= take
        return pieces
