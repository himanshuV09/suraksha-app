"""The faster free-space scan paths must behave exactly like the originals."""
import random

import pytest

from engine.allocation.unallocated_scanner import UnallocatedScanner


class ListReader:
    def __init__(self, chunks):
        self.chunks = chunks

    def iter_chunks(self):
        yield from self.chunks


def reference_windows(chunks, window_size, overlap_size):
    """The original scanner algorithm (re-slicing), kept as the oracle."""
    buffer, buffer_offset, expected, last_end = b"", None, None, None
    start_cluster = end_cluster = None
    step = window_size - overlap_size
    out = []
    for chunk in chunks:
        data, offset = chunk["data"], chunk["offset"]
        if not data:
            continue
        if buffer and offset != expected:
            if last_end is None or buffer_offset + len(buffer) > last_end:
                out.append((buffer, buffer_offset))
            buffer, buffer_offset, last_end = b"", None, None
        if not buffer:
            buffer_offset = offset
        buffer += data
        expected = offset + len(data)
        while len(buffer) >= window_size:
            out.append((buffer[:window_size], buffer_offset))
            last_end = buffer_offset + window_size
            buffer = buffer[step:]
            buffer_offset += step
    if buffer and (last_end is None or buffer_offset + len(buffer) > last_end):
        out.append((buffer, buffer_offset))
    return out


def random_chunks(rng):
    chunks, offset = [], rng.randrange(0, 4096)
    for _ in range(rng.randrange(1, 40)):
        size = rng.choice([1, 7, 64, 500, 4096, rng.randrange(1, 9000)])
        chunks.append({"data": rng.randbytes(size), "offset": offset})
        offset += size
        if rng.random() < 0.2:
            offset += rng.randrange(1, 10_000)  # a gap: next region
    return chunks


@pytest.mark.parametrize("seed", range(40))
def test_scanner_windows_match_the_original_algorithm(seed):
    rng = random.Random(seed)
    chunks = random_chunks(rng)
    window = rng.choice([16, 100, 1024, 4096])
    overlap = rng.randrange(0, window)

    windows = [
        (w["data"], w["offset"])
        for w in UnallocatedScanner(ListReader(chunks), window, overlap).scan()
    ]

    assert windows == reference_windows(chunks, window, overlap)
