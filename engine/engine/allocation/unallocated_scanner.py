
class UnallocatedScanner:
    """Scan unallocated bytes using bounded, overlapping windows."""

    def __init__(self, reader, window_size=64 * 1024, overlap_size=16):
        if reader is None:
            raise ValueError("reader cannot be None")

        if not isinstance(window_size, int) or isinstance(window_size, bool):
            raise TypeError("window_size must be an integer")
        if window_size <= 0:
            raise ValueError("window_size must be positive")

        if not isinstance(overlap_size, int) or isinstance(overlap_size, bool):
            raise TypeError("overlap_size must be an integer")
        if overlap_size < 0 or overlap_size >= window_size:
            raise ValueError(
                "overlap_size must be non-negative and smaller than window_size"
            )

        if not callable(getattr(reader, "iter_chunks", None)):
            raise TypeError("reader must provide iter_chunks()")

        self.reader = reader
        self.window_size = window_size
        self.overlap_size = overlap_size

    def scan(self):
        """Yield bounded windows with absolute offsets and exact overlap."""

        # Pending bytes are buffer[start:]. Advancing `start` instead of
        # re-slicing the buffer for every window avoids copying the rest
        # of the buffer each step (the scanner's main CPU cost before).
        buffer = bytearray()
        start = 0
        buffer_offset = None
        expected_offset = None
        last_emitted_end = None

        last_start_cluster = None
        last_end_cluster = None

        step = self.window_size - self.overlap_size

        def make_window(data, offset, start_cluster, end_cluster):
            return {
                "data": data,
                "offset": offset,
                "size": len(data),
                "start_cluster": start_cluster,
                "end_cluster": end_cluster,
            }

        for chunk in self.reader.iter_chunks():
            data = chunk.get("data")
            chunk_offset = chunk.get("offset")

            if not isinstance(data, bytes):
                raise TypeError("reader chunks must contain bytes")
            if (
                not isinstance(chunk_offset, int)
                or isinstance(chunk_offset, bool)
                or chunk_offset < 0
            ):
                raise ValueError("chunk offset must be a non-negative integer")
            if not data:
                continue

            pending = len(buffer) - start

            if pending and chunk_offset != expected_offset:
                # Finish the previous contiguous run before resetting.
                if (
                    buffer_offset is not None
                    and (
                        last_emitted_end is None
                        or buffer_offset + pending > last_emitted_end
                    )
                ):
                    yield make_window(
                        bytes(buffer[start:]), buffer_offset,
                        last_start_cluster, last_end_cluster,
                    )

                buffer = bytearray()
                start = 0
                pending = 0
                buffer_offset = None
                last_emitted_end = None

            if not pending:
                buffer_offset = chunk_offset

            # Drop consumed bytes once per chunk, not once per window.
            del buffer[:start]
            start = 0
            buffer += data
            expected_offset = chunk_offset + len(data)
            last_start_cluster = chunk.get("start_cluster")
            last_end_cluster = chunk.get("end_cluster")

            while len(buffer) - start >= self.window_size:
                window = bytes(buffer[start:start + self.window_size])

                yield make_window(
                    window, buffer_offset,
                    last_start_cluster, last_end_cluster,
                )

                last_emitted_end = buffer_offset + len(window)
                start += step
                buffer_offset += step

        # Emit only the tail containing bytes not covered by a full window.
        pending = len(buffer) - start
        if (
            pending
            and buffer_offset is not None
            and (
                last_emitted_end is None
                or buffer_offset + pending > last_emitted_end
            )
        ):
            yield make_window(
                bytes(buffer[start:]), buffer_offset,
                last_start_cluster, last_end_cluster,
            )
