import io

import pytest

from engine.allocation.carved_artifact import CarvedArtifact
from engine.allocation.carving_models import SignatureCandidate
from engine.allocation.carving_reader import CarvingReader
from engine.allocation.carver import Carver
from engine.allocation.candidate_extent_analyzer import (
    CandidateExtentAnalyzer,
)
from engine.allocation.extent_analysis import ExtentAnalysis
from engine.allocation.fragment_analyzer import FragmentAnalyzer
from engine.allocation.recovery_planner import RecoveryPlanner
from engine.allocation.recovery_plan import RecoveryPlan
from engine.allocation.unallocated_carving_service import (
    UnallocatedCarvingService,
)
from engine.allocation.validated_candidate import (
    ValidatedCandidate,
)

from engine.allocation.recovery_result import (
    RecoveryResult,
    RecoveryStatus,
)


def make_validated_candidate():
    candidate = SignatureCandidate(
        signature="JPEG",
        extension=".jpg",
        offset=4096,
        relative_offset=0,
        start_cluster=1,
        end_cluster=1,
        confidence=0.9,
    )

    return ValidatedCandidate(
        candidate=candidate,
        detected_size=8,
        validation_reason="JPEG structural validation passed",
    )


def test_contiguous_candidate_is_carved_end_to_end():
    image = io.BytesIO(
        b"\x00" * 4096
        + b"JPEGDATA"
        + b"\x00" * 4096
    )

    validated_candidate = make_validated_candidate()

    allocation_ranges = [
        {
            "start_cluster": 0,
            "end_cluster": 0,
            "cluster_count": 1,
            "state": "allocated",
        },
        {
            "start_cluster": 1,
            "end_cluster": 1,
            "cluster_count": 1,
            "state": "unallocated",
        },
        {
            "start_cluster": 2,
            "end_cluster": 2,
            "cluster_count": 1,
            "state": "allocated",
        },
    ]

    extent_analyzer = CandidateExtentAnalyzer(
        allocation_ranges=allocation_ranges,
        cluster_size=4096,
    )

    fragment_analyzer = FragmentAnalyzer(
        cluster_size=4096,
    )

    planner = RecoveryPlanner()

    carving_reader = CarvingReader(image)

    carver = Carver(carving_reader)

    service = UnallocatedCarvingService(
        extent_analyzer=extent_analyzer,
        fragment_analyzer=fragment_analyzer,
        recovery_planner=planner,
        carver=carver,
    )

    result = service.recover(
        validated_candidate
    )

    assert isinstance(
        result,
        RecoveryResult,
    )

    assert result.status == RecoveryStatus.RECOVERED

    assert result.recovered is True

    assert result.artifact is not None

    assert result.artifact.data == b"JPEGDATA"

    assert result.artifact.source_offset == 4096

    assert result.artifact.size == 8

    

def test_service_rejects_candidate_crossing_allocated_space():
    image = io.BytesIO(
        b"\x00" * 4096
        + b"JPEGDATA"
        + b"\x00" * 4096
    )

    validated_candidate = make_validated_candidate()

    allocation_ranges = [
        {
            "start_cluster": 0,
            "end_cluster": 0,
            "cluster_count": 1,
            "state": "allocated",
        },
        {
            "start_cluster": 1,
            "end_cluster": 1,
            "cluster_count": 1,
            "state": "unallocated",
        },
        {
            "start_cluster": 2,
            "end_cluster": 2,
            "cluster_count": 1,
            "state": "allocated",
        },
    ]

    # Make the candidate cross from cluster 1 into
    # allocated cluster 2.
    candidate = SignatureCandidate(
        signature="JPEG",
        extension=".jpg",
        offset=4096,
        relative_offset=0,
        start_cluster=1,
        end_cluster=2,
        confidence=0.9,
    )

    validated_candidate = ValidatedCandidate(
        candidate=candidate,
        detected_size=4097,
        validation_reason="Synthetic fragmented candidate",
    )

    extent_analyzer = CandidateExtentAnalyzer(
        allocation_ranges=allocation_ranges,
        cluster_size=4096,
    )

    fragment_analyzer = FragmentAnalyzer(
        cluster_size=4096,
    )

    planner = RecoveryPlanner()

    carver = Carver(
        CarvingReader(image)
    )

    service = UnallocatedCarvingService(
        extent_analyzer=extent_analyzer,
        fragment_analyzer=fragment_analyzer,
        recovery_planner=planner,
        carver=carver,
    )

    result = service.recover(
        validated_candidate
    )

    assert isinstance(
        result,
        RecoveryResult,
    )

    assert result.status == RecoveryStatus.ALLOCATED_CROSSING

    assert result.recovered is False

    assert result.artifact is None

    assert result.reason
            


def test_recover_many_returns_only_successfully_recovered_artifacts():
    image = io.BytesIO(
        b"\x00" * 4096
        + b"JPEGDATA"
        + b"\x00" * 4096
    )

    valid_candidate = make_validated_candidate()

    allocation_ranges = [
        {
            "start_cluster": 0,
            "end_cluster": 0,
            "cluster_count": 1,
            "state": "allocated",
        },
        {
            "start_cluster": 1,
            "end_cluster": 1,
            "cluster_count": 1,
            "state": "unallocated",
        },
        {
            "start_cluster": 2,
            "end_cluster": 2,
            "cluster_count": 1,
            "state": "allocated",
        },
    ]

    invalid_candidate = SignatureCandidate(
        signature="JPEG",
        extension=".jpg",
        offset=4096,
        relative_offset=0,
        start_cluster=1,
        end_cluster=2,
        confidence=0.9,
    )

    invalid_validated_candidate = ValidatedCandidate(
        candidate=invalid_candidate,
        detected_size=4097,
        validation_reason="Synthetic fragmented candidate",
    )

    extent_analyzer = CandidateExtentAnalyzer(
        allocation_ranges=allocation_ranges,
        cluster_size=4096,
    )

    fragment_analyzer = FragmentAnalyzer(
        cluster_size=4096,
    )

    planner = RecoveryPlanner()

    carver = Carver(
        CarvingReader(image)
    )

    service = UnallocatedCarvingService(
        extent_analyzer=extent_analyzer,
        fragment_analyzer=fragment_analyzer,
        recovery_planner=planner,
        carver=carver,
    )

    results = service.recover_many(
        [
            valid_candidate,
            invalid_validated_candidate,
        ]
    )

    assert len(results) == 2

    assert isinstance(
        results[0],
        RecoveryResult,
    )

    assert results[0].status == RecoveryStatus.RECOVERED

    assert results[0].artifact is not None

    assert results[0].artifact.data == b"JPEGDATA"


    assert isinstance(
        results[1],
        RecoveryResult,
    )

    assert results[1].status == RecoveryStatus.ALLOCATED_CROSSING

    assert results[1].artifact is None

    assert results[1].reason

def test_service_returns_recovered_result_for_contiguous_candidate():
    image = io.BytesIO(
        b"\x00" * 4096
        + b"JPEGDATA"
        + b"\x00" * 4096
    )

    validated_candidate = make_validated_candidate()

    allocation_ranges = [
        {
            "start_cluster": 0,
            "end_cluster": 0,
            "cluster_count": 1,
            "state": "allocated",
        },
        {
            "start_cluster": 1,
            "end_cluster": 1,
            "cluster_count": 1,
            "state": "unallocated",
        },
        {
            "start_cluster": 2,
            "end_cluster": 2,
            "cluster_count": 1,
            "state": "allocated",
        },
    ]

    extent_analyzer = CandidateExtentAnalyzer(
        allocation_ranges=allocation_ranges,
        cluster_size=4096,
    )

    fragment_analyzer = FragmentAnalyzer(
        cluster_size=4096,
    )

    planner = RecoveryPlanner()

    carver = Carver(
        CarvingReader(image)
    )

    service = UnallocatedCarvingService(
        extent_analyzer=extent_analyzer,
        fragment_analyzer=fragment_analyzer,
        recovery_planner=planner,
        carver=carver,
    )

    result = service.recover(
        validated_candidate
    )

    assert isinstance(
        result,
        RecoveryResult,
    )

    assert result.status == RecoveryStatus.RECOVERED

    assert result.recovered is True

    assert result.artifact is not None

    assert result.artifact.data == b"JPEGDATA"

def test_service_returns_fragmented_result_for_allocated_crossing():
    image = io.BytesIO(
        b"\x00" * 4096
        + b"JPEGDATA"
        + b"\x00" * 4096
    )

    candidate = SignatureCandidate(
        signature="JPEG",
        extension=".jpg",
        offset=4096,
        relative_offset=0,
        start_cluster=1,
        end_cluster=2,
        confidence=0.9,
    )

    validated_candidate = ValidatedCandidate(
        candidate=candidate,
        detected_size=4097,
        validation_reason="Synthetic fragmented candidate",
    )

    allocation_ranges = [
        {
            "start_cluster": 0,
            "end_cluster": 0,
            "cluster_count": 1,
            "state": "allocated",
        },
        {
            "start_cluster": 1,
            "end_cluster": 1,
            "cluster_count": 1,
            "state": "unallocated",
        },
        {
            "start_cluster": 2,
            "end_cluster": 2,
            "cluster_count": 1,
            "state": "allocated",
        },
    ]

    extent_analyzer = CandidateExtentAnalyzer(
        allocation_ranges=allocation_ranges,
        cluster_size=4096,
    )

    fragment_analyzer = FragmentAnalyzer(
        cluster_size=4096,
    )

    planner = RecoveryPlanner()

    carver = Carver(
        CarvingReader(image)
    )

    service = UnallocatedCarvingService(
        extent_analyzer=extent_analyzer,
        fragment_analyzer=fragment_analyzer,
        recovery_planner=planner,
        carver=carver,
    )

    result = service.recover(
        validated_candidate
    )

    assert isinstance(
        result,
        RecoveryResult,
    )

    assert result.status == RecoveryStatus.ALLOCATED_CROSSING

    assert result.recovered is False

    assert result.artifact is None

    assert result.reason