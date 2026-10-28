import hashlib

from database.case import Case
from database.case_database import Database
from database.repository import Repository
from database.recovered_artifact_repository import RecoveredArtifactRepository
from database.schema import DatabaseSchema

from engine.allocation.artifact_hasher import ArtifactHasher
from engine.allocation.artifact_provenance_factory import (
    ArtifactProvenanceFactory,
)
from engine.allocation.carved_artifact import CarvedArtifact
from engine.allocation.carver import Carver
from engine.allocation.carving_reader import CarvingReader
from engine.allocation.candidate_context_factory import CandidateContextFactory
from engine.allocation.candidate_extent_analyzer import (
    CandidateExtentAnalyzer,
)
from engine.allocation.carving_models import SignatureCandidate
from engine.allocation.fragment_analyzer import FragmentAnalyzer
from engine.allocation.recovered_artifact_assembler import (
    RecoveredArtifactAssembler,
)
from engine.allocation.recovery_planner import RecoveryPlanner
from engine.allocation.signature_validator import SignatureValidator
from engine.allocation.unallocated_carving_service import (
    UnallocatedCarvingService,
)
from engine.allocation.validated_candidate import ValidatedCandidate

from parsers.ntfs_parser import NTFSParser


JPEG_OFFSET = 741667563
JPEG_SIZE = 8154131


def test_real_jpeg_persists_recovered_artifact_metadata(
    real_image_path, tmp_path
):
    IMAGE_PATH = real_image_path
    database = Database()

    try:
        database.create_case(
            "Real Unallocated Persistence Test", directory=tmp_path
        )

        schema = DatabaseSchema(database)
        schema.create_schema()

        repository = Repository(database)

        case = Case()
        case.case_name = "Real Unallocated Persistence Test"
        case.image_path = IMAGE_PATH

        case_id = repository.insert_case(case)

        with open(IMAGE_PATH, "rb") as image:
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
                offset=JPEG_OFFSET,
                relative_offset=JPEG_OFFSET - regions[0].start_offset,
                start_cluster=regions[0].start_cluster,
                end_cluster=regions[0].end_cluster,
                confidence=0.5,
            )

            context_factory = CandidateContextFactory(
                image=image,
                regions=regions,
            )

            context = context_factory.create(candidate)

            validation = SignatureValidator().validate(context)

            assert validation.valid is True
            assert validation.detected_size == JPEG_SIZE

            validated_candidate = ValidatedCandidate(
                candidate=candidate,
                detected_size=validation.detected_size,
                validation_reason=validation.reason,
            )

            extent_analyzer = CandidateExtentAnalyzer(
                allocation_ranges=parser.allocation_ranges,
                cluster_size=parser.cluster_size,
            )

            extent_analysis = extent_analyzer.analyze(
                validated_candidate
            )

            assert extent_analysis.start_offset == JPEG_OFFSET
            assert extent_analysis.end_offset == (
                JPEG_OFFSET + JPEG_SIZE - 1
            )
            assert extent_analysis.start_cluster == 181071
            assert extent_analysis.end_cluster == 183061
            assert extent_analysis.cluster_count == 1991
            assert extent_analysis.all_unallocated is True
            assert extent_analysis.contiguous is True

            fragment_analyzer = FragmentAnalyzer(
                cluster_size=parser.cluster_size,
            )

            fragment_analysis = fragment_analyzer.analyze(
                extent_analysis
            )

            assert fragment_analysis.complete is True
            assert len(fragment_analysis.fragments) == 1

            recovery_planner = RecoveryPlanner()

            recovery_plan = recovery_planner.create_plan(
                validated_candidate,
                extent_analysis,
            )

            carving_reader = CarvingReader(image)

            carver = Carver(carving_reader)

            carving_service = UnallocatedCarvingService(
                extent_analyzer=extent_analyzer,
                fragment_analyzer=fragment_analyzer,
                recovery_planner=recovery_planner,
                carver=carver,
            )

            recovery_result = carving_service.recover(
                validated_candidate
            )

            assert recovery_result.recovered is True
            assert recovery_result.artifact is not None

            artifact = recovery_result.artifact

            assert artifact.signature == "JPEG"
            assert artifact.extension == ".jpg"
            assert artifact.source_offset == JPEG_OFFSET
            assert artifact.size == JPEG_SIZE
            assert len(artifact.data) == JPEG_SIZE
            assert artifact.data[:3] == b"\xFF\xD8\xFF"
            assert artifact.data[-2:] == b"\xFF\xD9"

            assembler = RecoveredArtifactAssembler(
                artifact_hasher=ArtifactHasher(),
                provenance_factory=ArtifactProvenanceFactory(),
            )

            record = assembler.assemble(
                artifact=artifact,
                context=context,
                extent_analysis=extent_analysis,
                source_image=IMAGE_PATH,
            )

            expected_hash = hashlib.sha256(
                artifact.data
            ).hexdigest()

            assert record.sha256 == expected_hash

            provenance = record.provenance

            assert provenance.source_image == IMAGE_PATH
            assert provenance.source_type == "UNALLOCATED"

            # Containing unallocated region.
            assert provenance.region_start_cluster == 167186
            assert provenance.region_end_cluster == 259984
            assert provenance.region_start_offset == 684793856

            # Actual physical artifact extent.
            assert provenance.start_cluster == 181071
            assert provenance.end_cluster == 183061

            assert provenance.source_offset == JPEG_OFFSET
            assert provenance.relative_offset == 56873707

            recovered_repository = RecoveredArtifactRepository(
                database
            )

            artifact_id = recovered_repository.create(
                case_id=case_id,
                record=record,
            )

            assert isinstance(artifact_id, int)
            assert artifact_id > 0

            persisted = recovered_repository.get(
                artifact_id
            )

            assert persisted is not None

            assert persisted.signature == "JPEG"
            assert persisted.extension == ".jpg"
            assert persisted.size == JPEG_SIZE
            assert persisted.sha256 == expected_hash
            assert persisted.confidence == 0.5

            assert persisted.source_image == IMAGE_PATH
            assert persisted.source_type == "UNALLOCATED"

            # Containing unallocated region.
            assert persisted.region_start_cluster == 167186
            assert persisted.region_end_cluster == 259984
            assert persisted.region_start_offset == 684793856

            # Actual physical artifact extent.
            assert persisted.start_cluster == 181071
            assert persisted.end_cluster == 183061

            assert persisted.source_offset == JPEG_OFFSET
            assert persisted.relative_offset == 56873707

            assert (
                persisted.validation_reason
                == validation.reason
            )

            persisted_artifacts = recovered_repository.list_by_case(
                case_id
            )

            assert len(persisted_artifacts) == 1

            persisted_from_list = persisted_artifacts[0]

            assert persisted_from_list.artifact_id == artifact_id
            assert persisted_from_list.signature == "JPEG"
            assert persisted_from_list.extension == ".jpg"
            assert persisted_from_list.size == JPEG_SIZE
            assert persisted_from_list.sha256 == expected_hash
            assert persisted_from_list.source_offset == JPEG_OFFSET

    finally:
        database.close()