import pytest

from engine.allocation.carving_models import SignatureCandidate
from engine.allocation.recovery_plan import RecoveryPlan
from engine.allocation.validated_candidate import ValidatedCandidate


def make_validated_candidate():
    candidate = SignatureCandidate(
        signature="JPEG",
        extension=".jpg",
        offset=1000,
        relative_offset=100,
        start_cluster=10,
        end_cluster=20,
        confidence=0.9,
    )

    return ValidatedCandidate(
        candidate=candidate,
        detected_size=500,
        validation_reason="JPEG structural validation passed",
    )


def test_recovery_plan_creation():
    validated = make_validated_candidate()

    plan = RecoveryPlan(
        candidate=validated,
        source_offset=1000,
        requested_size=500,
    )

    assert plan.source_offset == 1000
    assert plan.requested_size == 500
    assert plan.contiguous is True


def test_recovery_plan_requires_matching_offset():
    validated = make_validated_candidate()

    with pytest.raises(ValueError):
        RecoveryPlan(
            candidate=validated,
            source_offset=2000,
            requested_size=500,
        )


def test_recovery_plan_requires_matching_size():
    validated = make_validated_candidate()

    with pytest.raises(ValueError):
        RecoveryPlan(
            candidate=validated,
            source_offset=1000,
            requested_size=600,
        )


def test_recovery_plan_rejects_invalid_candidate():
    with pytest.raises(TypeError):
        RecoveryPlan(
            candidate=None,
            source_offset=1000,
            requested_size=500,
        )
        