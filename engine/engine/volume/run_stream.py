"""A read-only, seekable file object over an NTFS data-run list.

Reads go straight to the clusters that hold the requested bytes, so a
caller that needs only part of a file (``zipfile`` reads just the
central directory at the end of an archive) never loads the whole file.

Sparse runs and bytes past the initialized size read as zeros, as NTFS
defines them.
"""
import io
from bisect import bisect_right


class RunStream(io.RawIOBase):

    def __init__(self, image, geometry, runs, size, initialized_size=None):
        super().__init__()
        self._image = image
        self._size = max(0, size)
        initialized = self._size if initialized_size is None else initialized_size
        self._initialized = min(self._size, max(0, initialized))
        self._position = 0

        # (stream_start, stream_end, image_offset or None) per run.
        self._extents = []
        position = 0
        for run in runs:
            length = run["length"] * geometry.cluster_size
            image_offset = None if run["sparse"] else geometry.cluster_offset(run["lcn"])
            self._extents.append((position, position + length, image_offset))
            position += length
        self._starts = [start for start, _, _ in self._extents]

    @classmethod
    def for_evidence(cls, image, geometry, evidence):
        """The unnamed $DATA stream of a parsed file (resident or not)."""
        if evidence.resident_data is not None:
            return io.BytesIO(evidence.resident_data)
        return cls(image, geometry, evidence.data_runs, evidence.file_size)

    # -- io.RawIOBase ---------------------------------------------------

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self._position

    def seek(self, offset, whence=io.SEEK_SET):
        if whence == io.SEEK_CUR:
            offset += self._position
        elif whence == io.SEEK_END:
            offset += self._size
        if offset < 0:
            raise ValueError("negative seek position")
        self._position = offset
        return self._position

    def readinto(self, buffer):
        view = memoryview(buffer).cast("B")
        data = self.read_at(self._position, len(view))
        view[:len(data)] = data
        self._position += len(data)
        return len(data)

    @property
    def size(self):
        return self._size

    # -- random access ----------------------------------------------------

    def read_at(self, offset, length):
        """Read up to ``length`` bytes at ``offset`` without moving."""
        end = min(offset + length, self._size)
        if offset >= end:
            return b""

        data = bytearray()
        index = max(0, bisect_right(self._starts, offset) - 1)
        position = offset
        while position < end and index < len(self._extents):
            start, stop, image_offset = self._extents[index]
            if position >= stop:
                index += 1
                continue
            take = min(end, stop) - position
            if image_offset is None:
                data.extend(bytes(take))
            else:
                self._image.seek(image_offset + position - start)
                chunk = self._image.read(take)
                data.extend(chunk)
                if len(chunk) < take:
                    break  # truncated image
            position += take
            index += 1

        if end > self._initialized:
            zero_from = max(0, self._initialized - offset)
            data[zero_from:] = bytes(len(data) - zero_from)

        return bytes(data)
