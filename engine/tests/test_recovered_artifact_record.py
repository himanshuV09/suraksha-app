import hashlib

import pytest

from engine.allocation.artifact_provenance import ArtifactProvenance
from engine.allocation.carved_artifact import CarvedArtifact
from engine.allocation.carving_models import SignatureCandidate
from engine.allocation.recovered_artifact_record import (
    RecoveredArtifactRecord,
)
from engine.allocation.validated_candidate import ValidatedCandidate


def create_record():
    data = b"JPEGDATA"

    candidate = SignatureCandidate(
        signature="JPEG",
        extension=".jpg",
        offset=684794112,
        relative_offset=256,
        start_cluster=167186,
        end_cluster=167186,
        confidence=0.95,
    )

    validated_candidate = ValidatedCandidate(
        candidate=candidate,
        detected_size=len(data),
        validation_reason="JPEG structural validation passed",
    )

    artifact = CarvedArtifact(
        candidate=validated_candidate,
        data=data,
        source_offset=684794112,
        size=len(data),
    )

    provenance = ArtifactProvenance(
        source_image="test.001",
        source_type="UNALLOCATED",
        region_start_cluster=167186,
        region_end_cluster=259984,
        region_start_offset=684793856,
        source_offset=684794112,
        relative_offset=256,
        start_cluster=167186,
        end_cluster=167186,
    )

    sha256 = hashlib.sha256(data).hexdigest()

    return RecoveredArtifactRecord(
        artifact=artifact,
        sha256=sha256,
        provenance=provenance,
    )


def test_valid_record_is_created():
    record = create_record()

    assert isinstance(record, RecoveredArtifactRecord)
    assert record.signature == "JPEG"
    assert record.extension == ".jpg"
    assert record.size == 8
    assert record.sha256 == hashlib.sha256(b"JPEGDATA").hexdigest()
    assert record.provenance.source_type == "UNALLOCATED"


def test_record_exposes_recovered_data():
    record = create_record()

    assert record.data == b"JPEGDATA"


def test_invalid_hash_length_is_rejected():
    record = create_record()

    with pytest.raises(ValueError):
        RecoveredArtifactRecord(
            artifact=record.artifact,
            sha256="abc",
            provenance=record.provenance,
        )


def test_invalid_hash_characters_are_rejected():
    record = create_record()

    with pytest.raises(ValueError):
        RecoveredArtifactRecord(
            artifact=record.artifact,
            sha256="z" * 64,
            provenance=record.provenance,
        )


def test_source_offset_mismatch_is_rejected():
    record = create_record()

    mismatched_provenance = ArtifactProvenance(
        source_image="test.001",
        source_type="UNALLOCATED",
        region_start_cluster=167186,
        region_end_cluster=259984,
        region_start_offset=684793856,
        source_offset=684798208,
        relative_offset=4352,
        start_cluster=167187,
        end_cluster=167187,
    )

    with pytest.raises(ValueError):
        RecoveredArtifactRecord(
            artifact=record.artifact,
            sha256=record.sha256,
            provenance=mismatched_provenance,
        )


