import pytest

from engine.allocation.extent_analysis import (
    ExtentAnalysis,
)
from engine.allocation.fragment_analyzer import (
    FragmentAnalyzer,
)


def make_extent(states):
    return ExtentAnalysis(
        start_offset=8192,
        end_offset=8192 + (len(states) * 4096) - 1,
        start_cluster=2,
        end_cluster=2 + len(states) - 1,
        cluster_count=len(states),
        states=states,
        all_unallocated=all(
            state == "unallocated"
            for state in states
        ),
        contiguous=all(
            state == "unallocated"
            for state in states
        ),
    )


def test_single_unallocated_extent():
    analyzer = FragmentAnalyzer(cluster_size=4096)

    extent = make_extent(
        [
            "unallocated",
            "unallocated",
        ]
    )

    result = analyzer.analyze(extent)

    assert result.complete is True
    assert len(result.fragments) == 1
    assert result.fragments[0].sequence == 0
    assert result.fragments[0].source_offset == 8192
    assert result.fragments[0].size == 8192


def test_multiple_unallocated_fragments():
    analyzer = FragmentAnalyzer(cluster_size=4096)

    extent = make_extent(
        [
            "unallocated",
            "allocated",
            "unallocated",
        ]
    )

    result = analyzer.analyze(extent)

    assert result.complete is False
    assert len(result.fragments) == 2

    assert result.fragments[0].sequence == 0
    assert result.fragments[0].source_offset == 8192
    assert result.fragments[0].size == 4096

    assert result.fragments[1].sequence == 1
    assert result.fragments[1].source_offset == 16384
    assert result.fragments[1].size == 4096


def test_allocated_extent_has_no_recovery_fragments():
    analyzer = FragmentAnalyzer(cluster_size=4096)

    extent = make_extent(
        [
            "allocated",
            "allocated",
        ]
    )

    result = analyzer.analyze(extent)

    assert result.complete is False
    assert result.fragments == []


def test_requires_extent_analysis():
    analyzer = FragmentAnalyzer(cluster_size=4096)

    with pytest.raises(TypeError):
        analyzer.analyze(None)