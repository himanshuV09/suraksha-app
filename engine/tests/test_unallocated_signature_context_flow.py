
import io

from engine.allocation.allocation_models import UnallocatedRegion
from engine.allocation.unallocated_reader import UnallocatedReader
from engine.allocation.unallocated_scanner import UnallocatedScanner
from engine.allocation.signature_detector import SignatureDetector
from engine.allocation.candidate_context_factory import CandidateContextFactory


def main():
    # Create a synthetic image with one unallocated region.
    image_bytes = bytearray(200)

    region_start = 100
    region_end = 132  # Exclusive end: 32 bytes in the region.

    # Place a JPEG signature across a 4-byte reader-chunk boundary.
    jpeg_signature = b"\xFF\xD8\xFF"
    signature_offset = 103
    image_bytes[signature_offset:signature_offset + len(jpeg_signature)] = (
        jpeg_signature
    )

    image = io.BytesIO(bytes(image_bytes))

    region = UnallocatedRegion(
        start_cluster=10,
        end_cluster=17,
        cluster_count=8,
        start_offset=region_start,
        end_offset=region_end,
        byte_count=region_end - region_start,
        state="UNALLOCATED",
    )

    # 1. Verify the production reader reads only the specified region.
    reader = UnallocatedReader(
        image=image,
        ranges=[region],
        cluster_size=4,
        chunk_size=4,
    )

    chunks = list(reader.iter_chunks())

    assert chunks, "Reader returned no chunks"
    assert all(
        region_start <= chunk["offset"]
        and chunk["offset"] + chunk["size"] <= region_end
        for chunk in chunks
    ), "Reader returned bytes outside the region"

    assert b"".join(chunk["data"] for chunk in chunks) == bytes(
        image_bytes[region_start:region_end]
    )

    print("Production reader bounds: PASS")

    # 2. Verify the scanner preserves the absolute signature offset.
    scanner = UnallocatedScanner(
        reader=reader,
        window_size=8,
        overlap_size=2,
    )
    detector = SignatureDetector()

    candidates_by_identity = {}

    for window in scanner.scan():
        detected = detector.detect(
            window["data"],
            window["offset"],
        )

        for candidate in detected:
            identity = (candidate.signature, candidate.offset)
            candidates_by_identity[identity] = candidate

    candidates = list(candidates_by_identity.values())

    jpeg_candidates = [
        candidate
        for candidate in candidates
        if candidate.offset == signature_offset
        and candidate.signature.upper() == "JPEG"
    ]

    assert jpeg_candidates, (
        "Expected JPEG signature was not detected at its absolute offset. "
        f"Candidates found: "
        f"{[(c.signature, c.offset) for c in candidates]}"
    )

    candidate = jpeg_candidates[0]

    print("Production scanner and detector: PASS")

    # 3. Resolve the candidate into its containing unallocated region.
    # Do not use scanner-window cluster bounds as region bounds.
    from engine.allocation.carving_models import SignatureCandidate

    candidate_without_window_cluster_bounds = SignatureCandidate(
        signature=candidate.signature,
        extension=candidate.extension,
        offset=candidate.offset,
        relative_offset=candidate.relative_offset,
        start_cluster=None,
        end_cluster=None,
        confidence=candidate.confidence,
        metadata=dict(candidate.metadata),
    )

    factory = CandidateContextFactory(
        image=image,
        regions=[region],
    )

    context = factory.create(candidate_without_window_cluster_bounds)

    assert context.region is region
    assert context.absolute_offset == signature_offset
    assert context.relative_offset == signature_offset - region_start

    print("Candidate region resolution: PASS")

    # 4. Verify reads are bounded by the region's exclusive end.
    assert context.read(3) == jpeg_signature

    assert context.remaining_bytes == region_end - signature_offset

    try:
        context.read(context.remaining_bytes + 1)
    except ValueError:
        pass
    else:
        raise AssertionError("Context allowed a read beyond the region")

    print("Candidate context bounded reads: PASS")

    # An offset at the exclusive end must not resolve to this region.
    try:
        from engine.allocation.carving_models import SignatureCandidate

        outside_candidate = SignatureCandidate(
            signature="JPEG",
            extension="jpg",
            offset=region_end,
            relative_offset=region_end - region_start,
        )

        factory.create(outside_candidate)

    except LookupError:
        pass
    else:
        raise AssertionError(
            "Candidate at the exclusive region end was accepted"
        )

    print("Exclusive-end boundary: PASS")
    print("\nUnallocated signature-to-context integration: PASS")


if __name__ == "__main__":
    main()
