
import io

from engine.allocation.allocation_models import UnallocatedRegion
from engine.allocation.unallocated_reader import UnallocatedReader
from engine.allocation.unallocated_scanner import UnallocatedScanner
from engine.allocation.signature_detector import SignatureDetector
from engine.allocation.unallocated_signature_service import (
    UnallocatedSignatureService,
)


def main():
    # Use one synthetic unallocated region with known absolute offsets.
    region_start = 100
    region_size = 64
    cluster_size = 4

    image_data = bytearray(256)

    # Place JPEG signatures at two distinct offsets.
    jpeg_signature = b"\xFF\xD8\xFF"
    first_offset = region_start + 10
    second_offset = region_start + 26

    image_data[first_offset:first_offset + 3] = jpeg_signature
    image_data[second_offset:second_offset + 3] = jpeg_signature

    image = io.BytesIO(bytes(image_data))

    region = UnallocatedRegion(
        start_cluster=25,
        end_cluster=40,
        cluster_count=16,
        start_offset=region_start,
        end_offset=region_start + region_size,
        byte_count=region_size,
        state="UNALLOCATED",
    )

    # Small reader chunks and overlapping scanner windows make the test
    # exercise repeated coverage of the same absolute byte offsets.
    reader = UnallocatedReader(
        image=image,
        ranges=[region],
        cluster_size=cluster_size,
        chunk_size=8,
    )

    scanner = UnallocatedScanner(
        reader=reader,
        window_size=16,
        overlap_size=8,
    )

    detector = SignatureDetector()

    raw_detections = []

    print("\nScanner windows and detected candidates:")

    for window in scanner.scan():
        detected = detector.detect(window["data"], window["offset"])

        print(
            f"Window offset={window['offset']}, "
            f"size={window['size']}, "
            f"end={window['offset'] + window['size']}"
        )

        for candidate in detected:
            print(
                f"  {candidate.signature} "
                f"at absolute offset {candidate.offset}"
            )
            raw_detections.append(candidate)

    raw_identities = [
        (candidate.signature, candidate.offset)
        for candidate in raw_detections
    ]

    print("\nRaw candidate identities:", raw_identities)

    # Confirm the scanner really exposes at least one signature more
    # than once across its overlapping windows.
    raw_identities = [
        (candidate.signature, candidate.offset)
        for candidate in raw_detections
    ]

    assert raw_identities.count(("JPEG", first_offset)) > 1, (
        "Test setup did not produce a duplicate detection "
        "for the first JPEG signature"
    )

    assert raw_identities.count(("JPEG", second_offset)) > 1, (
        "Test setup did not produce a duplicate detection "
        "for the second JPEG signature"
    )

    print("Overlapping windows produce duplicate detections: PASS")

    # Now test the production service's deduplication.
    service = UnallocatedSignatureService(
        reader=reader,
        window_size=16,
    )

    candidates = service.scan()
    identities = [
        (candidate.signature, candidate.offset)
        for candidate in candidates
    ]

    assert identities.count(("JPEG", first_offset)) == 1, (
        "First JPEG candidate was not deduplicated"
    )

    assert identities.count(("JPEG", second_offset)) == 1, (
        "Second JPEG candidate was not deduplicated"
    )

    assert len(identities) == len(set(identities)), (
        "Duplicate candidate identities remain in service output"
    )

    print("Service candidate deduplication: PASS")

    # Ensure distinct offsets are preserved and remain absolute.
    jpeg_offsets = sorted(
        candidate.offset
        for candidate in candidates
        if candidate.signature == "JPEG"
    )

    assert first_offset in jpeg_offsets
    assert second_offset in jpeg_offsets
    assert first_offset != second_offset

    print("Distinct absolute offsets preserved: PASS")
    print("\nUnallocated signature deduplication test: PASS")


if __name__ == "__main__":
    main()
