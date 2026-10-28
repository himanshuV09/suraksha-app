import hashlib

from engine.allocation.carving_reader import CarvingReader
from engine.allocation.carver import Carver
from engine.allocation.candidate_context_factory import CandidateContextFactory
from engine.allocation.candidate_extent_analyzer import (
    CandidateExtentAnalyzer,
)
from engine.allocation.carving_models import SignatureCandidate
from engine.allocation.fragment_analyzer import FragmentAnalyzer
from engine.allocation.recovery_planner import RecoveryPlanner
from engine.allocation.unallocated_carving_service import (
    UnallocatedCarvingService,
)
from engine.allocation.unallocated_recovery_workflow import (
    UnallocatedRecoveryWorkflow,
)
from engine.allocation.recovery_result import RecoveryStatus
from engine.allocation.signature_validator import SignatureValidator
from engine.allocation.validated_candidate import ValidatedCandidate

from parsers.ntfs_parser import NTFSParser

from database.case import Case
from database.case_database import Database
from database.repository import Repository
from database.schema import DatabaseSchema


JPEG_OFFSET = 741667563


def build_recovery_service(parser, image):
    extent_analyzer = CandidateExtentAnalyzer(
        allocation_ranges=parser.allocation_ranges,
        cluster_size=parser.cluster_size,
    )

    fragment_analyzer = FragmentAnalyzer(
        cluster_size=parser.cluster_size,
    )

    recovery_planner = RecoveryPlanner()

    carving_reader = CarvingReader(image)

    carver = Carver(carving_reader)

    return UnallocatedCarvingService(
        extent_analyzer=extent_analyzer,
        fragment_analyzer=fragment_analyzer,
        recovery_planner=recovery_planner,
        carver=carver,
    )


def test_real_jpeg_unallocated_recovery_workflow(
    real_image_path, tmp_path
):
    IMAGE_PATH = real_image_path
    database = Database()

    try:
        database.create_case(
            "Real Unallocated Recovery Workflow Test"
        )

        schema = DatabaseSchema(database)
        schema.create_schema()

        repository = Repository(database)

        case = Case()
        case.case_name = (
            "Real Unallocated Recovery Workflow Test"
        )
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

            assert parser.cluster_size == 4096

            regions = parser.get_unallocated_regions()

            assert len(regions) == 3

            candidate = SignatureCandidate(
                signature="JPEG",
                extension=".jpg",
                offset=JPEG_OFFSET,
                relative_offset=(
                    JPEG_OFFSET
                    - regions[0].start_offset
                ),
                start_cluster=regions[0].start_cluster,
                end_cluster=regions[0].end_cluster,
                confidence=0.5,
            )

            context_factory = CandidateContextFactory(
                image=image,
                regions=regions,
            )

            context = context_factory.create(candidate)

            validator = SignatureValidator()

            validation = validator.validate(context)

            assert validation.valid is True
            assert validation.detected_size == 8154131

            validated_candidate = ValidatedCandidate(
                candidate=candidate,
                detected_size=validation.detected_size,
                validation_reason=validation.reason,
            )

            recovery_service = build_recovery_service(
                parser,
                image,
            )

            workflow = UnallocatedRecoveryWorkflow(
                recovery_service=recovery_service,
            )

            result = workflow.recover(
                image=image,
                region=regions[0],
                candidate=validated_candidate,
                source_image=IMAGE_PATH,
            )

            assert result.recovery.status == RecoveryStatus.RECOVERED

            assert result.artifact is not None

            assert result.artifact.signature == "JPEG"
            assert result.artifact.extension == ".jpg"

            assert result.artifact.source_offset == JPEG_OFFSET

            assert result.artifact.size == 8154131

            assert len(result.artifact.data) == 8154131

            assert result.artifact.data[:3] == b"\xff\xd8\xff"

            assert result.artifact.data[-2:] == b"\xff\xd9"

            expected_sha256 = hashlib.sha256(
                result.artifact.data
            ).hexdigest()

            assert result.sha256 == expected_sha256

            assert result.source_image == IMAGE_PATH

            assert result.source_type == "UNALLOCATED"

            assert (
                result.region_start_cluster
                == regions[0].start_cluster
            )

            assert (
                result.region_end_cluster
                == regions[0].end_cluster
            )

            assert (
                result.region_start_offset
                == regions[0].start_offset
            )

            assert (
                result.relative_offset
                == JPEG_OFFSET
                - regions[0].start_offset
            )

    finally:
        database.close()