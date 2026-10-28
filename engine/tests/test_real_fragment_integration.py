from engine.allocation.fragment_analyzer import FragmentAnalyzer
from engine.allocation.candidate_extent_analyzer import CandidateExtentAnalyzer
from engine.allocation.carving_models import SignatureCandidate
from engine.allocation.candidate_context_factory import CandidateContextFactory
from engine.allocation.validated_candidate import ValidatedCandidate

from parsers.ntfs_parser import NTFSParser

from database.case import Case
from database.case_database import Database
from database.schema import DatabaseSchema
from database.repository import Repository




def test_real_ntfs_fragment_analysis(real_image_path, tmp_path):
    IMAGE_PATH = real_image_path
    database = Database()

    try:
        database.create_case("Fragment Integration Test", directory=tmp_path)

        schema = DatabaseSchema(database)
        schema.create_schema()

        repository = Repository(database)

        case = Case()
        case.case_name = "Fragment Integration Test"
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

            allocation_ranges = parser.allocation_ranges
            cluster_size = parser.cluster_size

            assert cluster_size == 4096
            assert len(allocation_ranges) > 0

            regions = parser.get_unallocated_regions()

            assert len(regions) == 3

            region = regions[0]

            candidate = SignatureCandidate(
                signature="TEST",
                extension=".test",
                offset=region.start_offset,
                relative_offset=0,
                start_cluster=region.start_cluster,
                end_cluster=region.end_cluster,
                confidence=0.5,
            )

            context_factory = CandidateContextFactory(
                image=image,
                regions=regions,
            )

            context = context_factory.create(candidate)

            assert context.absolute_offset == region.start_offset
            assert context.relative_offset == 0

            validated_candidate = ValidatedCandidate(
                candidate=candidate,
                detected_size=cluster_size * 2,
                validation_reason="Synthetic integration candidate",
            )

            extent_analyzer = CandidateExtentAnalyzer(
                allocation_ranges=allocation_ranges,
                cluster_size=cluster_size,
            )

            extent_analysis = extent_analyzer.analyze(
                validated_candidate
            )

            assert extent_analysis.all_unallocated is True
            assert extent_analysis.cluster_count == 2

            fragment_analyzer = FragmentAnalyzer(
                cluster_size=cluster_size
            )

            fragment_analysis = fragment_analyzer.analyze(
                extent_analysis
            )

            assert fragment_analysis.complete is True
            assert len(fragment_analysis.fragments) == 1

            fragment = fragment_analysis.fragments[0]

            assert fragment.source_offset == region.start_offset
            assert fragment.size == cluster_size * 2
            assert fragment.sequence == 0

    finally:
        database.close()
