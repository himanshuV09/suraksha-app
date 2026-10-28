"""Read the contents of one NTFS attribute (resident or non-resident).

Sparse runs and bytes past the initialized size read as zeros, as NTFS
defines them. ``segments()`` skips sparse runs entirely, which matters
for $UsnJrnl:$J: its logical size is often gigabytes, almost all sparse.
"""

import os

from engine.volume.run_stream import RunStream

DEFAULT_CHUNK = 1024 * 1024


class AttributeStream:

    def __init__(self, image, geometry, attribute):
        self.image = image
        self.geometry = geometry
        self.attribute = attribute

        if attribute.is_compressed and not attribute.resident:
            raise ValueError("Compressed attributes are not supported")

        self._reader = None if attribute.resident else RunStream(
            image,
            geometry,
            attribute.runs,
            attribute.real_size,
            attribute.initialized_size or attribute.real_size,
        )

    @property
    def size(self):
        return self.attribute.size

    def _extents(self):
        """Yield (stream_offset, length, image_offset or None) per run."""
        cluster = self.geometry.cluster_size
        position = 0
        for run in self.attribute.runs:
            length = run["length"] * cluster
            image_offset = (
                None if run["sparse"]
                else self.geometry.cluster_offset(run["lcn"])
            )
            yield position, length, image_offset
            position += length

    def read(self, offset, length):
        """Read ``length`` bytes at ``offset`` (clipped to the stream size)."""
        end = min(offset + length, self.size)
        if offset >= end:
            return b""

        if self.attribute.resident:
            return bytes(self.attribute.content[offset:end])

        return self._reader.read_at(offset, end - offset)

    def read_all(self, limit=None):
        size = self.size if limit is None else min(self.size, limit)
        return self.read(0, size)

    def segments(self, chunk_size=DEFAULT_CHUNK):
        """Yield (stream_offset, bytes, continues_previous) for real data.

        Sparse runs produce no output. ``continues_previous`` tells the
        caller whether this chunk directly follows the previous one, so
        record parsers can carry partial records across chunk edges.
        """
        if self.attribute.resident:
            if self.size:
                yield 0, self.read(0, self.size), False
            return

        limit = min(self.size, self.attribute.initialized_size or self.size)
        previous_end = None
        for start, run_length, image_offset in self._extents():
            if image_offset is None or start >= limit:
                continue
            run_end = min(start + run_length, limit)
            position = start
            while position < run_end:
                take = min(chunk_size, run_end - position)
                self.image.seek(image_offset + position - start)
                chunk = self.image.read(take)
                if not chunk:
                    return
                yield position, chunk, previous_end == position
                position += len(chunk)
                previous_end = position
                if len(chunk) < take:
                    return  # truncated image

    @property
    def has_data(self):
        """False when every run is sparse (the stream is all zeros)."""
        if self.attribute.resident:
            return self.size > 0
        return any(not run["sparse"] for run in self.attribute.runs)

    def copy_to(self, handle, chunk_size=DEFAULT_CHUNK):
        """Write the logical stream to an open binary file; returns bytes.

        Sparse regions become holes in the output file (sparse files on
        NTFS), so a mostly-empty stream such as $UsnJrnl:$J keeps its
        offsets without using disk space for the zeros.
        """
        _mark_sparse(handle)
        for offset, chunk, _ in self.segments(chunk_size):
            handle.seek(offset)
            handle.write(chunk)
        handle.truncate(self.size)
        return self.size


def _mark_sparse(handle):
    """Best effort: flag an output file as sparse on Windows (NTFS).

    Other platforms create holes automatically when seeking past the end.
    """
    if os.name != "nt":
        return
    try:
        import ctypes
        import msvcrt
        from ctypes import wintypes

        FSCTL_SET_SPARSE = 0x000900C4
        returned = wintypes.DWORD()
        ctypes.windll.kernel32.DeviceIoControl(
            wintypes.HANDLE(msvcrt.get_osfhandle(handle.fileno())),
            FSCTL_SET_SPARSE, None, 0, None, 0, ctypes.byref(returned), None,
        )
    except Exception:
        pass  # a plain (non-sparse) file is still a correct export
