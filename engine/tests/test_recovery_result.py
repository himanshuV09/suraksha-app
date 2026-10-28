import pytest

from engine.allocation.carved_artifact import CarvedArtifact
from engine.allocation.recovery_result import (
    RecoveryResult,
    RecoveryStatus,
)


def test_recovered_result_requires_artifact():
    with pytest.raises(ValueError):
        RecoveryResult(
            status=RecoveryStatus.RECOVERED,
            reason="Recovered successfully",
        )


def test_failed_result_cannot_have_artifact():
    with pytest.raises(TypeError):
        RecoveryResult(
            status=RecoveryStatus.FRAGMENTED_UNSUPPORTED,
            artifact="invalid",
            reason="Candidate is fragmented",
        )


def test_recovered_result_is_valid():
    artifact = object.__new__(CarvedArtifact)

    result = RecoveryResult(
        status=RecoveryStatus.RECOVERED,
        artifact=artifact,
        reason="Recovered successfully",
    )

    assert result.status == RecoveryStatus.RECOVERED
    assert result.recovered is True
    assert result.artifact is artifact


def test_fragmented_result_is_valid():
    result = RecoveryResult(
        status=RecoveryStatus.FRAGMENTED_UNSUPPORTED,
        reason="Candidate crosses allocated space",
    )

    assert result.status == RecoveryStatus.FRAGMENTED_UNSUPPORTED
    assert result.recovered is False
    assert result.artifact is None

