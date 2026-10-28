import io

import pytest

from engine.allocation.allocation_models import UnallocatedRegion
from engine.allocation.artifact_provenance import (
    ArtifactProvenance,
)
from engine.allocation.artifact_provenance_factory import (
    ArtifactProvenanceFactory,
)
from engine.allocation.carving_models import SignatureCandidate
from engine.allocation.extent_analysis import ExtentAnalysis
from engine.allocation.unallocated_candidate_context import (
    UnallocatedCandidateContext,
)


def create_context():
    region = UnallocatedRegion(
        start_cluster=167186,
        end_cluster=259984,
        start_offset=684793856,
        end_offset=1064898560,
        cluster_count=92799,
        byte_count=380104704,
    )

    candidate = SignatureCandidate(
        signature="JPEG",
        extension=".jpg",
        offset=684794112,
        relative_offset=256,
        start_cluster=167186,
        end_cluster=259984,
        confidence=0.95,
    )

    image = io.BytesIO(b"\x00" * 4096)

    return UnallocatedCandidateContext(
        image=image,
        region=region,
        candidate=candidate,
    )


def create_extent_analysis():
    return ExtentAnalysis(
        start_offset=684794112,
        end_offset=684794119,
        start_cluster=167186,
        end_cluster=167186,
        cluster_count=1,
        states=["unallocated"],
        all_unallocated=True,
        contiguous=True,
    )


def test_factory_creates_provenance():
    context = create_context()
    extent_analysis = create_extent_analysis()

    factory = ArtifactProvenanceFactory()

    provenance = factory.create(
        context=context,
        extent_analysis=extent_analysis,
        source_image="test.001",
    )

    assert isinstance(
        provenance,
        ArtifactProvenance,
    )

    assert provenance.source_image == "test.001"
    assert provenance.source_type == "UNALLOCATED"
    assert provenance.region_start_cluster == 167186
    assert provenance.region_end_cluster == 259984
    assert provenance.region_start_offset == 684793856
    assert provenance.source_offset == 684794112
    assert provenance.relative_offset == 256
    assert provenance.start_cluster == 167186
    assert provenance.end_cluster == 167186


def test_factory_rejects_invalid_context():
    factory = ArtifactProvenanceFactory()

    with pytest.raises(TypeError):
        factory.create(
            context=object(),
            extent_analysis=create_extent_analysis(),
            source_image="test.001",
        )


def test_factory_rejects_invalid_extent_analysis():
    factory = ArtifactProvenanceFactory()

    with pytest.raises(TypeError):
        factory.create(
            context=create_context(),
            extent_analysis=object(),
            source_image="test.001",
        )


def test_factory_rejects_empty_source_image():
    factory = ArtifactProvenanceFactory()

    with pytest.raises(ValueError):
        factory.create(
            context=create_context(),
            extent_analysis=create_extent_analysis(),
            source_image="",
        )


def test_factory_rejects_mismatched_extent_offset():
    context = create_context()

    extent_analysis = ExtentAnalysis(
        start_offset=684794113,
        end_offset=684794120,
        start_cluster=167186,
        end_cluster=167186,
        cluster_count=1,
        states=["unallocated"],
        all_unallocated=True,
        contiguous=True,
    )

    factory = ArtifactProvenanceFactory()

    with pytest.raises(ValueError):
        factory.create(
            context=context,
            extent_analysis=extent_analysis,
            source_image="test.001",
        )