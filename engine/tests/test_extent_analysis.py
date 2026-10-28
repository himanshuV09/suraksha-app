import pytest

from engine.allocation.extent_analysis import ExtentAnalysis


def test_extent_analysis_valid():
    result = ExtentAnalysis(
        start_offset=8192,
        end_offset=12287,
        start_cluster=2,
        end_cluster=2,
        cluster_count=1,
        states=["unallocated"],
        all_unallocated=True,
        contiguous=True,
    )

    assert result.start_offset == 8192
    assert result.end_offset == 12287
    assert result.start_cluster == 2
    assert result.end_cluster == 2
    assert result.cluster_count == 1
    assert result.states == ["unallocated"]
    assert result.all_unallocated is True
    assert result.contiguous is True


def test_extent_analysis_rejects_wrong_cluster_count():
    with pytest.raises(ValueError):
        ExtentAnalysis(
            start_offset=8192,
            end_offset=12287,
            start_cluster=2,
            end_cluster=2,
            cluster_count=2,
            states=["unallocated"],
            all_unallocated=True,
            contiguous=True,
        )


def test_extent_analysis_rejects_wrong_state_result():
    with pytest.raises(ValueError):
        ExtentAnalysis(
            start_offset=8192,
            end_offset=12287,
            start_cluster=2,
            end_cluster=2,
            cluster_count=1,
            states=["allocated"],
            all_unallocated=True,
            contiguous=True,
        )


def test_extent_analysis_rejects_state_length_mismatch():
    with pytest.raises(ValueError):
        ExtentAnalysis(
            start_offset=8192,
            end_offset=12287,
            start_cluster=2,
            end_cluster=2,
            cluster_count=1,
            states=[],
            all_unallocated=True,
            contiguous=True,
        )