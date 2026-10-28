import pytest

from engine.allocation.carving_models import SignatureCandidate
from engine.allocation.validated_candidate import ValidatedCandidate
from engine.allocation.extent_analysis import ExtentAnalysis
from engine.allocation.recovery_planner import RecoveryPlanner
from engine.allocation.recovery_plan import RecoveryPlan


def make_candidate(offset=8192, size=4096):
    candidate = SignatureCandidate(
        signature="JPEG",
        extension=".jpg",
        offset=offset,
        relative_offset=0,
        start_cluster=2,
        end_cluster=2,
        confidence=0.9,
    )

    return ValidatedCandidate(
        candidate=candidate,
        detected_size=size,
        validation_reason="JPEG structural validation passed",
    )


def make_extent(
    start_offset=8192,
    end_offset=12287,
    start_cluster=2,
    end_cluster=2,
    states=None,
    all_unallocated=True,
    contiguous=True,
):
    if states is None:
        states = ["unallocated"]

    return ExtentAnalysis(
        start_offset=start_offset,
        end_offset=end_offset,
        start_cluster=start_cluster,
        end_cluster=end_cluster,
        cluster_count=len(states),
        states=states,
        all_unallocated=all_unallocated,
        contiguous=contiguous,
    )


def test_create_recovery_plan():
    planner = RecoveryPlanner()

    candidate = make_candidate()

    extent = make_extent()

    plan = planner.create_plan(
        candidate,
        extent,
    )

    assert isinstance(plan, RecoveryPlan)
    assert plan.source_offset == 8192
    assert plan.requested_size == 4096
    assert plan.contiguous is True


def test_rejects_allocated_extent():
    planner = RecoveryPlanner()

    candidate = make_candidate()

    extent = make_extent(
        states=["allocated"],
        all_unallocated=False,
        contiguous=False,
    )

    with pytest.raises(ValueError):
        planner.create_plan(
            candidate,
            extent,
        )


def test_rejects_non_contiguous_extent():
    planner = RecoveryPlanner()

    candidate = make_candidate()

    extent = ExtentAnalysis(
        start_offset=8192,
        end_offset=16383,
        start_cluster=2,
        end_cluster=3,
        cluster_count=2,
        states=["unallocated", "allocated"],
        all_unallocated=False,
        contiguous=False,
    )


    with pytest.raises(ValueError):
        planner.create_plan(
            candidate,
            extent,
        )


def test_rejects_mismatched_extent():
    planner = RecoveryPlanner()

    candidate = make_candidate()

    extent = make_extent(
        start_offset=4096,
        end_offset=8191,
    )

    with pytest.raises(ValueError):
        planner.create_plan(
            candidate,
            extent,
        )