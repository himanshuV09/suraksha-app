import io

import pytest

from engine.allocation.allocation_models import (
    UnallocatedRegion,
)

from engine.allocation.carving_models import (
    SignatureCandidate,
)

from engine.allocation.candidate_context_factory import (
    CandidateContextFactory,
)

from engine.allocation.unallocated_candidate_context import (
    UnallocatedCandidateContext,
)


def make_region(
    start_cluster,
    end_cluster,
    start_offset,
    byte_count,
):
    return UnallocatedRegion(
        start_cluster=start_cluster,
        end_cluster=end_cluster,
        cluster_count=(
            end_cluster
            - start_cluster
            + 1
        ),
        start_offset=start_offset,
        end_offset=(
            start_offset
            + byte_count
        ),
        byte_count=byte_count,
        state="UNALLOCATED",
    )


def test_factory_creates_context_for_valid_candidate():

    image = io.BytesIO(
        b"A" * 4096
    )

    region = make_region(
        start_cluster=100,
        end_cluster=101,
        start_offset=1000,
        byte_count=8192,
    )

    candidate = SignatureCandidate(
        signature="JPEG",
        extension=".jpg",
        offset=1500,
        relative_offset=500,
        start_cluster=100,
        end_cluster=101,
        confidence=0.5,
    )

    factory = CandidateContextFactory(
        image=image,
        regions=[region],
    )

    context = factory.create(
        candidate
    )

    assert isinstance(
        context,
        UnallocatedCandidateContext,
    )

    assert context.region == region

    assert context.candidate == candidate

    assert context.absolute_offset == 1500

    assert context.relative_offset == 500


def test_factory_rejects_candidate_outside_regions():

    image = io.BytesIO(
        b"A" * 4096
    )

    region = make_region(
        start_cluster=100,
        end_cluster=101,
        start_offset=1000,
        byte_count=8192,
    )

    candidate = SignatureCandidate(
        signature="JPEG",
        extension=".jpg",
        offset=20000,
        relative_offset=0,
        confidence=0.5,
    )

    factory = CandidateContextFactory(
        image=image,
        regions=[region],
    )

    with pytest.raises(
        LookupError
    ):
        factory.create(candidate)


def test_factory_rejects_invalid_candidate_type():

    image = io.BytesIO(
        b"A" * 4096
    )

    region = make_region(
        start_cluster=100,
        end_cluster=101,
        start_offset=1000,
        byte_count=8192,
    )

    factory = CandidateContextFactory(
        image=image,
        regions=[region],
    )

    with pytest.raises(
        TypeError
    ):
        factory.create("not-a-candidate")