import pytest

from engine.allocation.candidate_extent_analyzer import CandidateExtentAnalyzer
from engine.allocation.carving_models import SignatureCandidate
from engine.allocation.extent_analysis import ExtentAnalysis
from engine.allocation.fragment_analyzer import FragmentAnalyzer
from engine.allocation.validated_candidate import ValidatedCandidate
from engine.recovery.image_reader import ImageReader
from engine.volume.geometry import VolumeGeometry

PARTITION = 1024 * 1024
CLUSTER = 4096


def test_cluster_offset_includes_volume_offset():
    geometry = VolumeGeometry(volume_offset=PARTITION, cluster_size=CLUSTER)

    assert geometry.cluster_offset(0) == PARTITION
    assert geometry.cluster_offset(10) == PARTITION + 10 * CLUSTER


def test_cluster_at_is_inverse_of_cluster_offset():
    geometry = VolumeGeometry(volume_offset=PARTITION, cluster_size=CLUSTER)

    assert geometry.cluster_at(PARTITION) == 0
    assert geometry.cluster_at(PARTITION + 10 * CLUSTER + 5) == 10


def test_cluster_at_rejects_offsets_outside_the_volume():
    geometry = VolumeGeometry(
        volume_offset=PARTITION, cluster_size=CLUSTER, total_clusters=100
    )

    with pytest.raises(ValueError, match="before the NTFS volume"):
        geometry.cluster_at(PARTITION - 1)

    with pytest.raises(ValueError, match="past the end"):
        geometry.cluster_at(PARTITION + 100 * CLUSTER)


@pytest.mark.parametrize("bad", [-1, True, 1.5, "0"])
def test_geometry_rejects_invalid_volume_offset(bad):
    with pytest.raises((TypeError, ValueError)):
        VolumeGeometry(volume_offset=bad, cluster_size=CLUSTER)


def test_image_reader_reads_clusters_relative_to_the_partition(tmp_path):
    image = bytearray(PARTITION + 4 * CLUSTER)
    image[PARTITION + 2 * CLUSTER:PARTITION + 2 * CLUSTER + 5] = b"HELLO"
    path = tmp_path / "disk.img"
    path.write_bytes(image)

    with open(path, "rb") as handle:
        reader = ImageReader(handle, CLUSTER, volume_offset=PARTITION)
        assert reader.read_clusters(2, 1)[:5] == b"HELLO"


def _candidate(offset, size):
    return ValidatedCandidate(
        candidate=SignatureCandidate(
            signature="JPEG",
            extension=".jpg",
            offset=offset,
            relative_offset=0,
            confidence=0.5,
        ),
        detected_size=size,
        validation_reason="test",
    )


def test_extent_analyzer_maps_partitioned_offsets_to_volume_clusters():
    ranges = [
        {"start_cluster": 0, "end_cluster": 99, "cluster_count": 100, "state": "allocated"},
        {"start_cluster": 100, "end_cluster": 199, "cluster_count": 100, "state": "unallocated"},
    ]
    analyzer = CandidateExtentAnalyzer(ranges, CLUSTER, volume_offset=PARTITION)

    # A file stored in LCN 100-101 of a volume that starts 1 MiB into the disk.
    analysis = analyzer.analyze(_candidate(PARTITION + 100 * CLUSTER, CLUSTER + 1))

    assert (analysis.start_cluster, analysis.end_cluster) == (100, 101)
    assert analysis.all_unallocated is True


def test_extent_analyzer_without_volume_offset_would_misread_partitioned_disk():
    """Documents the original bug: ignoring the offset finds the wrong clusters."""
    ranges = [
        {"start_cluster": 0, "end_cluster": 99, "cluster_count": 100, "state": "allocated"},
        {"start_cluster": 100, "end_cluster": 999, "cluster_count": 900, "state": "unallocated"},
    ]
    wrong = CandidateExtentAnalyzer(ranges, CLUSTER, volume_offset=0)

    analysis = wrong.analyze(_candidate(PARTITION + 100 * CLUSTER, 10))

    assert analysis.start_cluster == 356  # 256 clusters too far


def test_extent_analyzer_reports_offsets_before_the_volume_as_lookup_error():
    analyzer = CandidateExtentAnalyzer([], CLUSTER, volume_offset=PARTITION)

    with pytest.raises(LookupError):
        analyzer.analyze(_candidate(10, 10))


def test_fragment_analyzer_reports_absolute_image_offsets():
    analysis = ExtentAnalysis(
        start_offset=PARTITION + 100 * CLUSTER,
        end_offset=PARTITION + 102 * CLUSTER - 1,
        start_cluster=100,
        end_cluster=101,
        cluster_count=2,
        states=["unallocated", "unallocated"],
        all_unallocated=True,
        contiguous=True,
    )

    result = FragmentAnalyzer(CLUSTER, volume_offset=PARTITION).analyze(analysis)

    assert result.fragments[0].source_offset == PARTITION + 100 * CLUSTER
