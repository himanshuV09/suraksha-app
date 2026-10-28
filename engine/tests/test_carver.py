from io import BytesIO

import pytest

from engine.allocation.carver import Carver
from engine.allocation.carving_models import SignatureCandidate
from engine.allocation.carving_reader import CarvingReader
from engine.allocation.recovery_plan import RecoveryPlan
from engine.allocation.validated_candidate import ValidatedCandidate
from engine.allocation.carved_artifact import CarvedArtifact


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
        detected_size=24,
        validation_reason="JPEG structural validation passed",
    )

    return RecoveryPlan(
        candidate=validated,
        source_offset=100,
        requested_size=24,
    )


def test_carver_recovers_artifact():
    image = BytesIO(
        b"\x00" * 100
        + b"\xFF\xD8\xFF"
        + b"RECOVERED-JPEG-DATA"
        + b"\xFF\xD9"
        + b"\x00" * 100
    )

    reader = CarvingReader(image)
    carver = Carver(reader)

    plan = make_plan()

    artifact = carver.carve(plan)

    assert isinstance(artifact, CarvedArtifact)
    assert artifact.signature == "JPEG"
    assert artifact.extension == ".jpg"
    assert artifact.source_offset == 100
    assert artifact.size == 24
    assert artifact.data == (
        b"\xFF\xD8\xFF"
        b"RECOVERED-JPEG-DATA"
        b"\xFF\xD9"
    )


def test_carver_rejects_invalid_plan():
    image = BytesIO(b"\x00" * 200)

    reader = CarvingReader(image)
    carver = Carver(reader)

    with pytest.raises(TypeError):
        carver.carve(None)


def test_carver_requires_carving_reader():
    with pytest.raises(ValueError):
        Carver(None)