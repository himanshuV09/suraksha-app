import pytest

from engine.allocation.artifact_provenance import ArtifactProvenance


def test_valid_provenance_is_created():
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

    assert provenance.source_image == "test.001"
    assert provenance.source_type == "UNALLOCATED"
    assert provenance.region_start_cluster == 167186
    assert provenance.region_end_cluster == 259984
    assert provenance.region_start_offset == 684793856
    assert provenance.source_offset == 684794112
    assert provenance.relative_offset == 256
    assert provenance.start_cluster == 167186
    assert provenance.end_cluster == 167186


def test_relative_offset_must_match_source_offset():
    with pytest.raises(ValueError):
        ArtifactProvenance(
            source_image="test.001",
            source_type="UNALLOCATED",
            region_start_cluster=167186,
            region_end_cluster=259984,
            region_start_offset=684793856,
            source_offset=684798208,
            relative_offset=0,
            start_cluster=167187,
            end_cluster=167187,
        )


def test_artifact_cannot_start_before_region():
    with pytest.raises(ValueError):
        ArtifactProvenance(
            source_image="test.001",
            source_type="UNALLOCATED",
            region_start_cluster=167186,
            region_end_cluster=259984,
            region_start_offset=684793856,
            source_offset=684793856,
            relative_offset=0,
            start_cluster=167185,
            end_cluster=167186,
        )


def test_artifact_cannot_end_after_region():
    with pytest.raises(ValueError):
        ArtifactProvenance(
            source_image="test.001",
            source_type="UNALLOCATED",
            region_start_cluster=167186,
            region_end_cluster=259984,
            region_start_offset=684793856,
            source_offset=684793856,
            relative_offset=0,
            start_cluster=167186,
            end_cluster=259985,
        )


def test_negative_values_are_rejected():
    with pytest.raises(ValueError):
        ArtifactProvenance(
            source_image="test.001",
            source_type="UNALLOCATED",
            region_start_cluster=167186,
            region_end_cluster=259984,
            region_start_offset=684793856,
            source_offset=-1,
            relative_offset=0,
            start_cluster=167186,
            end_cluster=167186,
        )


def test_empty_source_image_is_rejected():
    with pytest.raises(ValueError):
        ArtifactProvenance(
            source_image="",
            source_type="UNALLOCATED",
            region_start_cluster=167186,
            region_end_cluster=259984,
            region_start_offset=684793856,
            source_offset=684793856,
            relative_offset=0,
            start_cluster=167186,
            end_cluster=167186,
        )