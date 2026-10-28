from engine.allocation.signature_detector import SignatureDetector
from engine.allocation.unallocated_scanner import UnallocatedScanner


class ChunkReader:
    def __init__(self, chunks):
        self.chunks = chunks

    def iter_chunks(self):
        yield from self.chunks


def test_signature_split_across_reader_chunk_boundary_is_found():
    payload = b"AAAAAAA\xff\xd8\xffBBBBB"
    chunks = [
        {
            "data": payload[:8],
            "offset": 0,
            "size": 8,
            "start_cluster": 0,
            "end_cluster": 3,
        },
        {
            "data": payload[8:],
            "offset": 8,
            "size": len(payload) - 8,
            "start_cluster": 0,
            "end_cluster": 3,
        },
    ]
    scanner = UnallocatedScanner(
        reader=ChunkReader(chunks),
        window_size=8,
        overlap_size=7,
    )
    detector = SignatureDetector()
    candidates = []
    for window in scanner.scan():
        candidates.extend(detector.detect(window["data"], window["offset"]))

    jpeg_offsets = {
        candidate.offset
        for candidate in candidates
        if candidate.signature == "JPEG"
    }
    assert 7 in jpeg_offsets
