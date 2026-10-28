
import io

from engine.allocation.allocation_models import UnallocatedRegion
from engine.allocation.carving_models import SignatureCandidate
from engine.allocation.candidate_region_resolver import CandidateRegionResolver
from engine.allocation.candidate_context_factory import CandidateContextFactory


def make_region():
    # The region covers bytes 100 through 199.
    # end_offset is exclusive.
    return UnallocatedRegion(
        start_cluster=10,
        end_cluster=10,
        cluster_count=1,
        start_offset=100,
        end_offset=200,
        byte_count=100,
        state="UNALLOCATED",
    )


def make_candidate(offset):
    return SignatureCandidate(
        signature="JPEG",
        extension=".jpg",
        offset=offset,
        relative_offset=0,
        start_cluster=None,
        end_cluster=None,
        confidence=0.5,
        metadata={"source": "UNALLOCATED"},
    )


def main():
    region = make_region()
    image = io.BytesIO(b"\x00" * 300)

    factory = CandidateContextFactory(
        image=image,
        regions=[region],
    )

    # Valid candidate: exactly at the region's first byte.
    first = factory.create(make_candidate(100))
    assert first.absolute_offset == 100
    assert first.remaining_bytes == 100

    # Valid candidate: one byte before the exclusive end.
    last = factory.create(make_candidate(199))
    assert last.remaining_bytes == 1
    assert last.read(1) == b"\x00"

    # Candidate at the exclusive end must be rejected.
    try:
        factory.create(make_candidate(200))
    except LookupError:
        pass
    else:
        raise AssertionError(
            "Candidate at exclusive region end was incorrectly accepted"
        )

    # A read cannot extend beyond the region.
    try:
        last.read(2)
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Read beyond region boundary was incorrectly accepted"
        )

    # Check the resolver's direct boundary behavior too.
    resolver = CandidateRegionResolver([region])
    try:
        resolver.resolve(make_candidate(200))
    except LookupError:
        pass
    else:
        raise AssertionError(
            "Resolver accepted candidate at exclusive region end"
        )

    print("Candidate context boundary test: PASS")


if __name__ == "__main__":
    main()
