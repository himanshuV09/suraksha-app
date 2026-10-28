import pytest

from engine.allocation.carving_models import SignatureCandidate
from engine.allocation.validated_candidate import ValidatedCandidate
from engine.allocation.candidate_extent_analyzer import (
    CandidateExtentAnalyzer,
)


def make_candidate(offset=8192, size=4096):
    candidate = SignatureCandidate(
        signature="JPEG",
        extension=".jpg",
        offset=offset,
        relative_offset=0,
        start_cluster=2,
        end_cluster=3,
        confidence=0.9,
    )

    return ValidatedCandidate(
        candidate=candidate,
        detected_size=size,
        validation_reason="JPEG structural validation passed",
    )


def make_ranges():
    return [
        {
            "start_cluster": 0,
            "cluster_count": 2,
            "end_cluster": 1,
            "state": "allocated",
        },
        {
            "start_cluster": 2,
            "cluster_count": 4,
            "end_cluster": 5,
            "state": "unallocated",
        },
        {
            "start_cluster": 6,
            "cluster_count": 2,
            "end_cluster": 7,
            "state": "allocated",
        },
    ]


def test_candidate_inside_unallocated_clusters():
    analyzer = CandidateExtentAnalyzer(
        allocation_ranges=make_ranges(),
        cluster_size=4096,
    )

    candidate = make_candidate(
        offset=8192,
        size=4096,
    )

    result = analyzer.analyze(candidate)

    assert result.start_cluster == 2
    assert result.end_cluster == 2
    assert result.cluster_count == 1
    assert result.states == ["unallocated"]
    assert result.all_unallocated is True
    assert result.contiguous is True


def test_candidate_spanning_multiple_unallocated_clusters():
    analyzer = CandidateExtentAnalyzer(
        allocation_ranges=make_ranges(),
        cluster_size=4096,
    )

    candidate = make_candidate(
        offset=8192,
        size=8192,
    )

    result = analyzer.analyze(candidate)

    assert result.start_cluster == 2
    assert result.end_cluster == 3
    assert result.cluster_count == 2
    assert result.states == [
        "unallocated",
        "unallocated",
    ]
    assert result.all_unallocated is True


def test_candidate_crossing_allocated_space():
    analyzer = CandidateExtentAnalyzer(
        allocation_ranges=make_ranges(),
        cluster_size=4096,
    )

    candidate = make_candidate(
        offset=20480,
        size=8192,
    )

    result = analyzer.analyze(candidate)

    assert result.start_cluster == 5
    assert result.end_cluster == 6
    assert result.states == [
        "unallocated",
        "allocated",
    ]
    assert result.all_unallocated is False
    assert result.contiguous is False


def test_candidate_requires_validated_candidate():
    analyzer = CandidateExtentAnalyzer(
        allocation_ranges=make_ranges(),
        cluster_size=4096,
    )

    with pytest.raises(TypeError):
        analyzer.analyze(None)