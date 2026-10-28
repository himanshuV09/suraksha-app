
import io

from engine.allocation.allocation_models import UnallocatedRegion
from engine.allocation.unallocated_reader import UnallocatedReader
from engine.allocation.unallocated_signature_service import (
    UnallocatedSignatureService,
)


def make_region(start_cluster, start_offset, payload):
    return UnallocatedRegion(
        start_cluster=start_cluster,
        end_cluster=start_cluster + 7,
        cluster_count=8,
        start_offset=start_offset,
        end_offset=start_offset + 32,
        byte_count=32,
        state="UNALLOCATED",
    )


def main():
    image_data = bytearray(256)

    valid_offset = 100
    invalid_offset = 160

    # Candidate 1: JPEG signature followed by EOI.
    valid_payload = (
        b"\xFF\xD8\xFF\xE0"
        + b"\x00" * 8
        + b"\xFF\xD9"
    )

    # Candidate 2: JPEG signature but no EOI.
    invalid_payload = (
        b"\xFF\xD8\xFF\xE0"
        + b"\x00" * 28
    )

    image_data[valid_offset:valid_offset + len(valid_payload)] = valid_payload
    image_data[invalid_offset:invalid_offset + len(invalid_payload)] = invalid_payload

    image = io.BytesIO(bytes(image_data))

    regions = [
        make_region(10, valid_offset, valid_payload),
        make_region(25, invalid_offset, invalid_payload),
    ]

    reader = UnallocatedReader(
        image=image,
        ranges=regions,
        cluster_size=4,
        chunk_size=4,
    )

    service = UnallocatedSignatureService(
        reader=reader,
        window_size=64,
    )

    # Detection should find both JPEG-like signatures.
    candidates = service.scan()

    assert any(c.offset == valid_offset for c in candidates), (
        "Valid-region signature was not detected"
    )
    assert any(c.offset == invalid_offset for c in candidates), (
        "Invalid-region signature was not detected"
    )

    print(f"Detected candidates: {len(candidates)}")
    print("Signature detection: PASS")

    # Configure the actual candidate-context factory.
    service.configure_candidate_context_factory(
        image=image,
        regions=regions,
    )

    validated = service.scan_and_validate_candidates(candidates)

    # Only the candidate with an EOI marker should pass
    # the current JPEG structural heuristic.
    validated_offsets = {item.offset for item in validated}

    assert valid_offset in validated_offsets, (
        "Expected candidate was not validated"
    )
    assert invalid_offset not in validated_offsets, (
        "Candidate without EOI was incorrectly validated"
    )

    print(f"Validated candidates: {len(validated)}")
    print("Valid/invalid candidate separation: PASS")

    for item in validated:
        assert item.detected_size > 0
        assert item.validation_reason.strip()

    print("ValidatedCandidate output: PASS")
    print("\nUnallocated signature service integration: PASS")


if __name__ == "__main__":
    main()
