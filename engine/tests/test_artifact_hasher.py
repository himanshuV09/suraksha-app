import hashlib

import pytest

from engine.allocation.artifact_hasher import ArtifactHasher
from engine.allocation.carved_artifact import CarvedArtifact
from engine.allocation.signature_detector import SignatureCandidate
from engine.allocation.validated_candidate import ValidatedCandidate


def create_artifact(data: bytes) -> CarvedArtifact:
    candidate = SignatureCandidate(
        signature="JPEG",
        extension=".jpg",
        offset=1000,
        relative_offset=0,
        start_cluster=10,
        end_cluster=10,
        confidence=0.95,
    )

    validated_candidate = ValidatedCandidate(
        candidate=candidate,
        detected_size=len(data),
        validation_reason="JPEG structural validation passed",
    )

    return CarvedArtifact(
        candidate=validated_candidate,
        data=data,
        source_offset=1000,
        size=len(data),
    )


def test_sha256_returns_correct_hash():
    artifact = create_artifact(b"JPEGDATA")

    hasher = ArtifactHasher()

    result = hasher.sha256(artifact)

    expected = hashlib.sha256(b"JPEGDATA").hexdigest()

    assert result == expected
    assert len(result) == 64


def test_sha256_is_deterministic():
    artifact = create_artifact(b"JPEGDATA")

    hasher = ArtifactHasher()

    first = hasher.sha256(artifact)
    second = hasher.sha256(artifact)

    assert first == second


def test_sha256_changes_when_artifact_data_changes():
    artifact_a = create_artifact(b"JPEGDATA")
    artifact_b = create_artifact(b"JPEGDATA2")

    hasher = ArtifactHasher()

    hash_a = hasher.sha256(artifact_a)
    hash_b = hasher.sha256(artifact_b)

    assert hash_a != hash_b


def test_sha256_rejects_invalid_artifact():
    hasher = ArtifactHasher()

    with pytest.raises(TypeError):
        hasher.sha256(b"not an artifact")