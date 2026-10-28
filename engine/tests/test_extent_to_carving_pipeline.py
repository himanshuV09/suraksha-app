import io

from engine.allocation.carving_models import SignatureCandidate
from engine.allocation.validated_candidate import ValidatedCandidate
from engine.allocation.candidate_extent_analyzer import (
    CandidateExtentAnalyzer,
)
from engine.allocation.recovery_planner import RecoveryPlanner
from engine.allocation.carving_reader import CarvingReader
from engine.allocation.carver import Carver
from engine.allocation.carved_artifact import CarvedArtifact


def make_candidate():
    candidate = SignatureCandidate(
        signature="JPEG",
        extension=".jpg",
        offset=8192,
        relative_offset=0,
        start_cluster=2,
        end_cluster=2,
        confidence=0.9,
    )

    return ValidatedCandidate(
        candidate=candidate,
        detected_size=4096,
        validation_reason="JPEG structural validation passed",
    )


def make_allocation_ranges():
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


def test_extent_to_carving_pipeline():
    image_data = bytearray(32768)

    recovered_data = b"JPEG_RECOVERED_DATA"

    image_data[8192:8192 + len(recovered_data)] = recovered_data

    image = io.BytesIO(bytes(image_data))

    candidate = make_candidate()

    analyzer = CandidateExtentAnalyzer(
        allocation_ranges=make_allocation_ranges(),
        cluster_size=4096,
    )

    extent_analysis = analyzer.analyze(candidate)

    assert extent_analysis.all_unallocated is True
    assert extent_analysis.contiguous is True

    planner = RecoveryPlanner()

    plan = planner.create_plan(
        candidate,
        extent_analysis,
    )

    reader = CarvingReader(image)

    carver = Carver(reader)

    artifact = carver.carve(plan)

    assert isinstance(artifact, CarvedArtifact)
    assert artifact.source_offset == 8192
    assert artifact.size == 4096
    assert artifact.data[:len(recovered_data)] == recovered_data
    assert artifact.signature == "JPEG"
    assert artifact.extension == ".jpg"