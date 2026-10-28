import pytest

from engine.allocation.recovery_fragment import (
    RecoveryFragment,
)


def test_recovery_fragment_valid():
    fragment = RecoveryFragment(
        source_offset=8192,
        size=4096,
        sequence=0,
    )

    assert fragment.source_offset == 8192
    assert fragment.size == 4096
    assert fragment.sequence == 0


def test_recovery_fragment_rejects_negative_offset():
    with pytest.raises(ValueError):
        RecoveryFragment(
            source_offset=-1,
            size=4096,
            sequence=0,
        )


def test_recovery_fragment_rejects_invalid_size():
    with pytest.raises(ValueError):
        RecoveryFragment(
            source_offset=8192,
            size=0,
            sequence=0,
        )


def test_recovery_fragment_rejects_negative_sequence():
    with pytest.raises(ValueError):
        RecoveryFragment(
            source_offset=8192,
            size=4096,
            sequence=-1,
        )