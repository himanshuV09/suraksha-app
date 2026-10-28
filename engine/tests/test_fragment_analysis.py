import pytest

from engine.allocation.fragment_analysis import (
    FragmentAnalysis,
)
from engine.allocation.recovery_fragment import (
    RecoveryFragment,
)


def make_fragments():
    return [
        RecoveryFragment(
            source_offset=8192,
            size=4096,
            sequence=0,
        ),
        RecoveryFragment(
            source_offset=16384,
            size=4096,
            sequence=1,
        ),
    ]


def test_fragment_analysis_valid():
    result = FragmentAnalysis(
        fragments=make_fragments(),
        complete=True,
    )

    assert len(result.fragments) == 2
    assert result.fragments[0].sequence == 0
    assert result.fragments[1].sequence == 1
    assert result.complete is True


def test_fragment_analysis_allows_empty_fragments():
    result = FragmentAnalysis(
        fragments=[],
        complete=False,
    )

    assert result.fragments == []
    assert result.complete is False


def test_fragment_analysis_rejects_invalid_fragment_type():
    with pytest.raises(TypeError):
        FragmentAnalysis(
            fragments=[object()],
            complete=False,
        )


def test_fragment_analysis_rejects_bad_sequence_order():
    fragments = [
        RecoveryFragment(
            source_offset=8192,
            size=4096,
            sequence=1,
        ),
        RecoveryFragment(
            source_offset=16384,
            size=4096,
            sequence=0,
        ),
    ]

    with pytest.raises(ValueError):
        FragmentAnalysis(
            fragments=fragments,
            complete=True,
        )