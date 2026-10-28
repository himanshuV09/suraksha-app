from io import BytesIO

import pytest

from engine.allocation.carving_models import SignatureCandidate
from engine.allocation.recovery_plan import RecoveryPlan
from engine.allocation.validated_candidate import ValidatedCandidate
from engine.allocation.carving_reader import CarvingReader


def make_plan():
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
        detected_size=20,
        validation_reason="JPEG structural validation passed",
    )

    return RecoveryPlan(
        candidate=validated,
        source_offset=100,
        requested_size=20,
    )


def test_carving_reader_reads_exact_planned_size():
    image = BytesIO(b"\x00" * 100 + b"A" * 20 + b"B" * 50)

    reader = CarvingReader(image)
    plan = make_plan()

    data = reader.read(plan)

    assert data == b"A" * 20
    assert len(data) == 20


def test_carving_reader_rejects_invalid_plan():
    image = BytesIO(b"\x00" * 200)

    reader = CarvingReader(image)

    with pytest.raises(TypeError):
        reader.read(None)


def test_carving_reader_detects_short_read():
    image = BytesIO(b"\x00" * 110)

    reader = CarvingReader(image)
    plan = make_plan()

    with pytest.raises(IOError):
        reader.read(plan)