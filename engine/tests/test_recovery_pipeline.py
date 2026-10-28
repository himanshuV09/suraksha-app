from io import BytesIO

from engine.allocation.carving_models import SignatureCandidate
from engine.allocation.validated_candidate import ValidatedCandidate
from engine.allocation.recovery_plan import RecoveryPlan
from engine.allocation.carving_reader import CarvingReader


def test_validated_candidate_to_recovery_plan_to_reader():
    image = BytesIO(
        b"\x00" * 100
        + b"\xFF\xD8\xFF"
        + b"RECOVERED-JPEG-DATA"
        + b"\xFF\xD9"
        + b"\x00" * 100
    )

    candidate = SignatureCandidate(
        signature="JPEG",
        extension=".jpg",
        offset=100,
        relative_offset=0,
        start_cluster=0,
        end_cluster=1,
        confidence=0.9,
    )

    validated = ValidatedCandidate(
        candidate=candidate,
        detected_size=24,
        validation_reason="JPEG structural validation passed",
    )

    plan = RecoveryPlan(
        candidate=validated,
        source_offset=100,
        requested_size=24,
    )

    reader = CarvingReader(image)

    recovered = reader.read(plan)

    assert recovered == (
        b"\xFF\xD8\xFF"
        b"RECOVERED-JPEG-DATA"
        b"\xFF\xD9"
    )

    assert len(recovered) == 24