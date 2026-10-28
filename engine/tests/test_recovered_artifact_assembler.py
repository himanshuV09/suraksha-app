import hashlib
import io

import pytest

from engine.allocation.allocation_models import UnallocatedRegion
from engine.allocation.artifact_hasher import ArtifactHasher
from engine.allocation.artifact_provenance_factory import (
    ArtifactProvenanceFactory,
)
from engine.allocation.carved_artifact import CarvedArtifact
from engine.allocation.carving_models import SignatureCandidate
from engine.allocation.extent_analysis import ExtentAnalysis
from engine.allocation.recovered_artifact_assembler import (
    RecoveredArtifactAssembler,
)
from engine.allocation.recovered_artifact_record import (
    RecoveredArtifactRecord,
)
from engine.allocation.unallocated_candidate_context import (
    UnallocatedCandidateContext,
)
from engine.allocation.validated_candidate import (
    ValidatedCandidate,
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

    image = io.BytesIO(
        b"\x00" * 4096
    )

    return UnallocatedCandidateContext(
        image=image,
        region=region,
        candidate=candidate,
    )


def create_validated_candidate():
    candidate = SignatureCandidate(
        signature="JPEG",
        extension=".jpg",
        offset=684794112,
        relative_offset=256,
        start_cluster=167186,
        end_cluster=259984,
        confidence=0.95,
    )

    return ValidatedCandidate(
        candidate=candidate,
        detected_size=9,
        validation_reason=(
            "JPEG structural validation passed"
        ),
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


def create_artifact():
    validated_candidate = (
        create_validated_candidate()
    )

    data = (
        b"\xFF\xD8\xFF"
        b"\xE0\x00\x10\x00"
        b"\xFF\xD9"
    )

    return CarvedArtifact(
        candidate=validated_candidate,
        data=data,
        source_offset=684794112,
        size=len(data),
    )


def create_assembler():
    return RecoveredArtifactAssembler(
        artifact_hasher=ArtifactHasher(),
        provenance_factory=ArtifactProvenanceFactory(),
    )


def test_assembler_creates_recovered_artifact_record():

    artifact = create_artifact()
    context = create_context()
    extent_analysis = create_extent_analysis()

    assembler = create_assembler()

    record = assembler.assemble(
        artifact=artifact,
        context=context,
        extent_analysis=extent_analysis,
        source_image="test.001",
    )

    assert isinstance(
        record,
        RecoveredArtifactRecord,
    )

    expected_hash = hashlib.sha256(
        artifact.data
    ).hexdigest()

    assert record.sha256 == expected_hash

    assert record.provenance.source_image == "test.001"


def test_assembler_preserves_artifact_identity():

    artifact = create_artifact()
    context = create_context()
    extent_analysis = create_extent_analysis()

    assembler = create_assembler()

    record = assembler.assemble(
        artifact=artifact,
        context=context,
        extent_analysis=extent_analysis,
        source_image="test.001",
    )

    assert record.artifact is artifact
    assert record.signature == "JPEG"
    assert record.extension == ".jpg"
    assert record.size == len(artifact.data)
    assert record.confidence == 0.95


def test_assembler_preserves_provenance():

    artifact = create_artifact()
    context = create_context()
    extent_analysis = create_extent_analysis()

    assembler = create_assembler()

    record = assembler.assemble(
        artifact=artifact,
        context=context,
        extent_analysis=extent_analysis,
        source_image="test.001",
    )

    provenance = record.provenance

    assert provenance.source_image == "test.001"
    assert provenance.source_type == "UNALLOCATED"

    assert (
        provenance.region_start_cluster
        == 167186
    )

    assert (
        provenance.region_end_cluster
        == 259984
    )

    assert (
        provenance.region_start_offset
        == 684793856
    )

    assert (
        provenance.source_offset
        == 684794112
    )

    assert (
        provenance.relative_offset
        == 256
    )

    assert provenance.start_cluster == 167186
    assert provenance.end_cluster == 167186


def test_assembler_rejects_invalid_artifact():

    assembler = create_assembler()

    with pytest.raises(TypeError):
        assembler.assemble(
            artifact=object(),
            context=create_context(),
            extent_analysis=create_extent_analysis(),
            source_image="test.001",
        )


def test_assembler_rejects_invalid_context():

    assembler = create_assembler()

    with pytest.raises(TypeError):
        assembler.assemble(
            artifact=create_artifact(),
            context=object(),
            extent_analysis=create_extent_analysis(),
            source_image="test.001",
        )


def test_assembler_rejects_invalid_extent_analysis():

    assembler = create_assembler()

    with pytest.raises(TypeError):
        assembler.assemble(
            artifact=create_artifact(),
            context=create_context(),
            extent_analysis=object(),
            source_image="test.001",
        )


def test_assembler_rejects_empty_source_image():

    assembler = create_assembler()

    with pytest.raises(ValueError):
        assembler.assemble(
            artifact=create_artifact(),
            context=create_context(),
            extent_analysis=create_extent_analysis(),
            source_image="",
        )


def test_assembler_rejects_mismatched_extent():

    artifact = create_artifact()
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

    assembler = create_assembler()

    with pytest.raises(ValueError):
        assembler.assemble(
            artifact=artifact,
            context=context,
            extent_analysis=extent_analysis,
            source_image="test.001",
        )


def test_assembler_rejects_mismatched_artifact_context():

    context = create_context()

    candidate = SignatureCandidate(
        signature="JPEG",
        extension=".jpg",
        offset=684794113,
        relative_offset=257,
        start_cluster=167186,
        end_cluster=259984,
        confidence=0.95,
    )

    validated_candidate = ValidatedCandidate(
        candidate=candidate,
        detected_size=9,
        validation_reason=(
            "JPEG structural validation passed"
        ),
    )

    artifact = CarvedArtifact(
        candidate=validated_candidate,
        data=(
            b"\xFF\xD8\xFF"
            b"\xE0\x00\x10\x00"
            b"\xFF\xD9"
        ),
        source_offset=684794113,
        size=9,
    )

    assembler = create_assembler()

    with pytest.raises(ValueError):
        assembler.assemble(
            artifact=artifact,
            context=context,
            extent_analysis=ExtentAnalysis(
                start_offset=684794113,
                end_offset=684794120,
                start_cluster=167186,
                end_cluster=167186,
                cluster_count=1,
                states=["unallocated"],
                all_unallocated=True,
                contiguous=True,
            ),
            source_image="test.001",
        )

def test_real_jpeg_assembler_preserves_physical_extent(
    real_image_path, tmp_path
):
    from engine.allocation.candidate_context_factory import (
        CandidateContextFactory,
    )
    from engine.allocation.candidate_extent_analyzer import (
        CandidateExtentAnalyzer,
    )
    from engine.allocation.signature_validator import (
        SignatureValidator,
    )

    from parsers.ntfs_parser import NTFSParser

    from database.case import Case
    from database.case_database import Database
    from database.repository import Repository
    from database.schema import DatabaseSchema

    image_path = real_image_path

    jpeg_offset = 741667563

    database = Database()

    try:
        database.create_case(
            "Real Assembler Integration Test"
        )

        schema = DatabaseSchema(database)
        schema.create_schema()

        repository = Repository(database)

        case = Case()
        case.case_name = "Real Assembler Integration Test"
        case.image_path = image_path

        case_id = repository.insert_case(case)

        with open(image_path, "rb") as image:
            parser = NTFSParser(
                image,
                repository,
                case_id,
            )

            parser.parse_boot_sector()
            parser.enumerate_records()
            parser.analyze_allocation()

            regions = parser.get_unallocated_regions()

            assert len(regions) == 3

            candidate = SignatureCandidate(
                signature="JPEG",
                extension=".jpg",
                offset=jpeg_offset,
                relative_offset=(
                    jpeg_offset
                    - regions[0].start_offset
                ),
                start_cluster=(
                    regions[0].start_cluster
                ),
                end_cluster=(
                    regions[0].end_cluster
                ),
                confidence=0.5,
            )

            context_factory = CandidateContextFactory(
                image=image,
                regions=regions,
            )

            context = context_factory.create(
                candidate
            )

            validation = SignatureValidator().validate(
                context
            )

            assert validation.valid is True
            assert validation.detected_size == 8154131

            validated_candidate = ValidatedCandidate(
                candidate=candidate,
                detected_size=validation.detected_size,
                validation_reason=validation.reason,
            )

            extent_analyzer = CandidateExtentAnalyzer(
                allocation_ranges=(
                    parser.allocation_ranges
                ),
                cluster_size=parser.cluster_size,
            )

            extent_analysis = extent_analyzer.analyze(
                validated_candidate
            )

            assert extent_analysis.start_cluster == 181071
            assert extent_analysis.end_cluster == 183061
            assert extent_analysis.start_offset == jpeg_offset
            assert extent_analysis.cluster_count == 1991
            assert extent_analysis.all_unallocated is True
            assert extent_analysis.contiguous is True

            image.seek(jpeg_offset)

            data = image.read(
                validated_candidate.detected_size
            )

            assert len(data) == 8154131

            artifact = CarvedArtifact(
                candidate=validated_candidate,
                data=data,
                source_offset=jpeg_offset,
                size=len(data),
            )

            assembler = create_assembler()

            record = assembler.assemble(
                artifact=artifact,
                context=context,
                extent_analysis=extent_analysis,
                source_image=image_path,
            )

            assert record.sha256 == hashlib.sha256(
                data
            ).hexdigest()

            provenance = record.provenance

            assert (
                provenance.region_start_cluster
                == 167186
            )

            assert (
                provenance.region_end_cluster
                == 259984
            )

            assert (
                provenance.start_cluster
                == 181071
            )

            assert (
                provenance.end_cluster
                == 183061
            )

            assert (
                provenance.source_offset
                == jpeg_offset
            )

            assert (
                provenance.relative_offset
                == 56873707
            )

    finally:
        database.close()