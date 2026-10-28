import pytest

from engine.allocation.carving_models import SignatureCandidate
from engine.allocation.validated_candidate import ValidatedCandidate
from engine.allocation.carved_artifact import CarvedArtifact


def make_candidate():
    candidate = SignatureCandidate(
        signature="JPEG",
        extension=".jpg",
        offset=1000,
        relative_offset=0,
        start_cluster=10,
        end_cluster=20,
        confidence=0.9,
    )

    return ValidatedCandidate(
        candidate=candidate,
        detected_size=10,
        validation_reason="JPEG structural validation passed",
    )


def test_carved_artifact_creation():
    candidate = make_candidate()
    data = b"1234567890"

    artifact = CarvedArtifact(
        candidate=candidate,
        data=data,
        source_offset=1000,
        size=10,
    )

    assert artifact.data == data
    assert artifact.size == 10
    assert artifact.source_offset == 1000
    assert artifact.signature == "JPEG"
    assert artifact.extension == ".jpg"
    assert artifact.confidence == 0.9


def test_carved_artifact_rejects_size_mismatch():
    candidate = make_candidate()

    with pytest.raises(ValueError):
        CarvedArtifact(
            candidate=candidate,
            data=b"1234567890",
            source_offset=1000,
            size=9,
        )


def test_carved_artifact_rejects_offset_mismatch():
    candidate = make_candidate()

    with pytest.raises(ValueError):
        CarvedArtifact(
            candidate=candidate,
            data=b"1234567890",
            source_offset=2000,
            size=10,
        )


def test_carved_artifact_rejects_candidate_size_mismatch():
    candidate = make_candidate()

    with pytest.raises(ValueError):
        CarvedArtifact(
            candidate=candidate,
            data=b"123456789",
            source_offset=1000,
            size=9,
        )