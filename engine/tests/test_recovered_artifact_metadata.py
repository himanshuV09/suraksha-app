import pytest

from engine.allocation.recovered_artifact_metadata import (
    RecoveredArtifactMetadata,
)


def test_recovered_artifact_metadata_contains_persisted_identity():

    metadata = RecoveredArtifactMetadata(
        artifact_id=1,
        signature="JPEG",
        extension=".jpg",
        size=9,
        sha256=(
            "0123456789abcdef"
            "0123456789abcdef"
            "0123456789abcdef"
            "0123456789abcdef"
        ),
        confidence=0.95,
        source_image="test.001",
        source_type="UNALLOCATED",
        region_start_cluster=167186,
        region_end_cluster=259984,
        region_start_offset=684793856,
        source_offset=684794112,
        relative_offset=256,
        start_cluster=167186,
        end_cluster=167186,
        validation_reason="JPEG structural validation passed",
    )

    assert metadata.signature == "JPEG"
    assert metadata.extension == ".jpg"
    assert metadata.size == 9
    assert metadata.sha256 == (
        "0123456789abcdef"
        "0123456789abcdef"
        "0123456789abcdef"
        "0123456789abcdef"
    )

    assert metadata.source_image == "test.001"
    assert metadata.source_type == "UNALLOCATED"

    assert metadata.region_start_cluster == 167186
    assert metadata.region_end_cluster == 259984
    assert metadata.region_start_offset == 684793856

    assert metadata.source_offset == 684794112
    assert metadata.relative_offset == 256

    assert metadata.start_cluster == 167186
    assert metadata.end_cluster == 167186

    assert metadata.validation_reason == (
        "JPEG structural validation passed"
    )

def test_metadata_rejects_invalid_sha256():
    with pytest.raises(ValueError):
        RecoveredArtifactMetadata(
            artifact_id=1,
            signature="JPEG",
            extension=".jpg",
            size=9,
            sha256="invalid",
            confidence=0.95,
            source_image="test.001",
            source_type="UNALLOCATED",
            region_start_cluster=167186,
            region_end_cluster=259984,
            region_start_offset=684793856,
            source_offset=684794112,
            relative_offset=256,
            start_cluster=167186,
            end_cluster=167186,
            validation_reason="JPEG structural validation passed",
        )


def test_metadata_rejects_invalid_relative_offset():
    with pytest.raises(ValueError):
        RecoveredArtifactMetadata(
            artifact_id=1,
            signature="JPEG",
            extension=".jpg",
            size=9,
            sha256=(
                "0123456789abcdef"
                "0123456789abcdef"
                "0123456789abcdef"
                "0123456789abcdef"
            ),
            confidence=0.95,
            source_image="test.001",
            source_type="UNALLOCATED",
            region_start_cluster=167186,
            region_end_cluster=259984,
            region_start_offset=684793856,
            source_offset=684794112,
            relative_offset=999,
            start_cluster=167186,
            end_cluster=167186,
            validation_reason="JPEG structural validation passed",
        )


def test_metadata_rejects_invalid_cluster_range():
    with pytest.raises(ValueError):
        RecoveredArtifactMetadata(
            artifact_id=1,
            signature="JPEG",
            extension=".jpg",
            size=9,
            sha256=(
                "0123456789abcdef"
                "0123456789abcdef"
                "0123456789abcdef"
                "0123456789abcdef"
            ),
            confidence=0.95,
            source_image="test.001",
            source_type="UNALLOCATED",
            region_start_cluster=259984,
            region_end_cluster=167186,
            region_start_offset=684793856,
            source_offset=684794112,
            relative_offset=256,
            start_cluster=167186,
            end_cluster=167186,
            validation_reason="JPEG structural validation passed",
        )

def test_metadata_accepts_artifact_id():
    metadata = RecoveredArtifactMetadata(
        artifact_id=1,
        signature="JPEG",
        extension=".jpg",
        size=100,
        sha256="a" * 64,
        confidence=0.95,
        source_image="test.001",
        source_type="UNALLOCATED",
        region_start_cluster=100,
        region_end_cluster=200,
        region_start_offset=409600,
        source_offset=409856,
        relative_offset=256,
        start_cluster=101,
        end_cluster=101,
        validation_reason="JPEG structural validation passed",
    )

    assert metadata.artifact_id == 1

def test_metadata_rejects_non_positive_artifact_id():
    with pytest.raises(ValueError):
        RecoveredArtifactMetadata(
            artifact_id=0,
            signature="JPEG",
            extension=".jpg",
            size=100,
            sha256="a" * 64,
            confidence=0.95,
            source_image="test.001",
            source_type="UNALLOCATED",
            region_start_cluster=100,
            region_end_cluster=200,
            region_start_offset=409600,
            source_offset=409856,
            relative_offset=256,
            start_cluster=101,
            end_cluster=101,
            validation_reason="JPEG structural validation passed",
        )

def test_metadata_rejects_non_integer_artifact_id():
    with pytest.raises(TypeError):
        RecoveredArtifactMetadata(
            artifact_id="1",
            signature="JPEG",
            extension=".jpg",
            size=100,
            sha256="a" * 64,
            confidence=0.95,
            source_image="test.001",
            source_type="UNALLOCATED",
            region_start_cluster=100,
            region_end_cluster=200,
            region_start_offset=409600,
            source_offset=409856,
            relative_offset=256,
            start_cluster=101,
            end_cluster=101,
            validation_reason="JPEG structural validation passed",
        )