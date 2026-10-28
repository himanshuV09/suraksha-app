
import io

from engine.allocation.allocation_models import UnallocatedRegion
from engine.allocation.carving_models import SignatureCandidate
from engine.allocation.unallocated_candidate_context import (
    UnallocatedCandidateContext,
)
from engine.allocation.signature_validator import SignatureValidator


def make_context(payload):
    region_start = 100
    region_size = max(32, len(payload))
    region_end = region_start + region_size

    image_data = bytearray(region_end + 20)
    image_data[region_start:region_start + len(payload)] = payload

    image = io.BytesIO(bytes(image_data))

    region = UnallocatedRegion(
        start_cluster=10,
        end_cluster=10 + (region_size // 4) - 1,
        cluster_count=region_size // 4,
        start_offset=region_start,
        end_offset=region_end,
        byte_count=region_size,
        state="UNALLOCATED",
    )

    candidate = SignatureCandidate(
        signature="JPEG",
        extension="jpg",
        offset=region_start,
        relative_offset=0,
        confidence=1.0,
    )

    return UnallocatedCandidateContext(image, region, candidate)

def make_minimal_jpeg():
    """Build a minimal JPEG marker stream with valid segment lengths."""
    soi = b"\xFF\xD8"
    # APP0 marker with a length of 4 bytes, including the length field.
    app0 = b"\xFF\xE0\x00\x04AB"
    # A minimal DQT segment: length 4 for this test fixture.
    dqt = b"\xFF\xDB\x00\x04CD"
    # A minimal SOF0 segment with a length of 11 bytes.
    # Precision=8, height=1, width=1, one component.
    sof0 = (
        b"\xFF\xC0\x00\x0B"
        b"\x08\x00\x01\x00\x01\x01\x01\x11\x00"
    )
    # A minimal SOS segment with one component.
    sos = b"\xFF\xDA\x00\x08\x01\x01\x00\x00\x3F\x00"
    # Entropy-coded data followed by EOI.
    scan = b"\x11\x22\xFF\x00\x33"
    eoi = b"\xFF\xD9"
    return soi + app0 + dqt + sof0 + sos + scan + eoi

def main():
    jpeg = make_minimal_jpeg()
    context = make_context(jpeg)

    validator = SignatureValidator(read_chunk_size=8)
    result = validator.validate(context)

    assert result.valid, result.reason
    assert result.detected_size == len(jpeg), result
    print("Structurally valid JPEG: PASS")

    validated = validator.to_validated_candidate(context)
    assert validated is not None
    assert validated.detected_size == len(jpeg)
    print("Validated candidate creation: PASS")

    # Missing EOI must be rejected.
    missing_eoi = make_context(jpeg[:-2])
    result = validator.validate(missing_eoi)
    assert not result.valid
    assert result.detected_size is None
    print("Missing EOI rejection: PASS")

    # EOI beyond the configured scan limit must not be accepted.
    limited_validator = SignatureValidator(
        max_candidate_size=8,
        read_chunk_size=4,
    )
    result = limited_validator.validate(context)
    assert not result.valid
    print("Maximum candidate size: PASS")

    # A malformed segment length must be rejected.
    malformed = (
        b"\xFF\xD8"
        b"\xFF\xE0\x00\x01"  # Invalid: segment length is less than 2.
        b"\xFF\xD9"
    )
    result = validator.validate(make_context(malformed))
    assert not result.valid
    print("Malformed segment-length rejection: PASS")

    print("\nSignature validator tests: PASS")

def test_jpeg_start_signature_mismatch():
    # This candidate is labelled JPEG, but its bytes do not begin
    # with the expected FF D8 FF signature.
    context = make_context(
        b"NOT" + b"\x00" * 4 + b"\xFF\xD9"
    )

    validator = SignatureValidator(read_chunk_size=8)
    result = validator.validate(context)

    assert not result.valid
    assert result.detected_size is None
    assert result.reason == "JPEG start signature mismatch"

    print("JPEG start-signature rejection: PASS")



if __name__ == "__main__":
    test_jpeg_start_signature_mismatch()
    main()
