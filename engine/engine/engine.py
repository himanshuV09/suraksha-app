from datetime import datetime
import os
from database.case import Case
from database.case_database import Database
from database.schema import DatabaseSchema
from database.repository import Repository

from .analysis_result import AnalysisResult
from .volume.opener import open_ntfs_volume
from .volume.run_stream import RunStream
from .metafiles.analyzer import MetafileAnalyzer, MetafileReport
from database.metafile_repository import MetafileRepository
from database.deleted_file_repository import DeletedFileRepository
from .recovery.deleted_files import assess_deleted_files, summarize as summarize_deleted

from .pipeline.evidence_pipeline import EvidencePipeline
from .pipeline.pipeline_context import PipelineContext
from .recovery.image_reader import ImageReader
from .pipeline.stages.container_stage import ContainerStage
from .pipeline.stages.timeline_stage import TimelineStage
from .pipeline.stages.risk_stage import RiskStage


from .defaults import DEFAULT_CASE_NAME, DEFAULT_INVESTIGATOR
from .version import ENGINE_VERSION
from . import progress


class ForensicEngine:

    def __init__(
        self,
        case_name=DEFAULT_CASE_NAME,
        investigator=DEFAULT_INVESTIGATOR,
        cases_dir=None,
        description="",
    ):

        self.case_name = case_name
        self.investigator = investigator
        self.description = description
        # None means engine.paths.DEFAULT_CASES_DIR.
        self.cases_dir = cases_dir

        self.case = None

        self.database = None

        self.schema = None

        self.repository = None

        self.case_id = None

        self.parser = None

        self.result = AnalysisResult()

        self.pipeline = EvidencePipeline()

        self.pipeline.add_stage(
            ContainerStage()
        )

        self.pipeline.add_stage(
            TimelineStage()
        )

        self.pipeline.add_stage(
            RiskStage()
        )

    def initialize_case(
        self,
        image_path
    ):

        case = Case()

        case.case_name = self.case_name

        case.image_path = os.path.abspath(image_path)

        case.created_at = datetime.now()

        case.investigator = self.investigator

        case.description = self.description or "NTFS Evidence Analysis"

        case.status = "running"

        case.engine_version = ENGINE_VERSION

        self.case = case

    def initialize_case_database(self):

        self.database = Database()

        self.database.create_case(
            self.case.case_name,
            directory=self.cases_dir,
        )

        self.result.database_path = self.database.database_path

        self.schema = DatabaseSchema(
            self.database
        )

        self.schema.create_schema()

        self.repository = Repository(
            self.database
        )

        self.case_id = self.repository.insert_case(
            self.case
        )

        self.case.case_id = self.case_id

    def initialize_parser(
        self,
        image_path
    ):

        self.image = open(
            image_path,
            "rb"
        )

        self.parser = open_ntfs_volume(
            self.image,
            self.repository,
            self.case_id,
        )

        print("Detected filesystem:", self.parser.detected_boot_info["oem_id"])
        print("Volume offset:", self.parser.volume_offset)
        print("Partition info:", self.parser.partition_info)

    def analyze(
    self,
    image_path
):


        # open_ntfs_volume() has already parsed the boot sector.
        boot_info = self.parser.ntfs_info

        #
        # Image Information
        #
        self.result.filesystem = "NTFS"

        self.result.sector_size = (
            boot_info["bytes_per_sector"]
        )

        self.result.cluster_size = (
            self.parser.cluster_size
        )

        self.result.serial_number = str(
            boot_info["serial_number"]
        )

        #
        # Optional (when implemented)
        #
        # self.result.volume_label = ...

        #
        # Image Size
        #

        self.result.image_size = os.path.getsize(
            image_path
        )

        #
        # Parse Records
        #
        stats = self.parser.enumerate_records()

        # Persist NTFS unallocated-region metadata.
        # enumerate_records() must finish allocation analysis first.
        regions = self.parser.get_unallocated_regions()

        self.repository.replace_unallocated_regions(
            case_id=self.case_id,
            image_path=image_path,
            regions=regions,
        )

        image_reader = ImageReader.for_parser(self.parser)


        context = PipelineContext(

            image_reader=image_reader,

            repository=self.repository,

            case=self.case

        )


        progress.report("Listing container files and building the timeline", force=True)

        self.pipeline.execute(

            self.parser.evidence_objects,

            context

        )

        progress.report("Parsing NTFS metafiles", force=True)

        # NTFS metafiles: volume details, USN journal, $LogFile, $I30.
        # Runs after enumeration so their events get full paths.
        metafiles = self.analyze_metafiles()
        context.timeline_events.extend(metafiles.timeline_events)

        progress.report("Grading deleted files", force=True)

        deleted_summary, deleted_warnings = self.assess_deleted_files()

        progress.report("Saving results", force=True)

        self.parser.record_processor.save_all()

        self.repository.insert_timeline_events(

            self.case.case_id,

            context.timeline_events

        )

        self.result.total_records = (
            stats["total_records"]
        )

        self.result.total_files = (
            stats["total_files"]
        )

        self.result.total_directories = (
            stats["total_directories"]
        )

        self.result.deleted_files = (
            stats["deleted_files"]
        )

        self.result.fragmented_files = (
            stats["fragmented_files"]
        )

        self.result.ads_files = (
            stats["ads_files"]
        )

        self.result.timeline_events = len(context.timeline_events)

        self.result.corrupt_records = stats["corrupt_records"]
        self.result.record_error_count = stats["record_error_count"]
        self.result.record_errors = stats["record_errors"]
        self.result.warnings = list(stats["warnings"])

        self.result.volume_label = metafiles.volume_label
        self.result.metafile_counts = metafiles.counts
        self.result.warnings += metafiles.warnings

        self.result.deleted_recovery = deleted_summary
        self.result.warnings += deleted_warnings

    def assess_deleted_files(self):
        """Grade every deleted file against $Bitmap and store the result.

        Returns (summary dict, warnings list); never fails the analysis.
        """
        try:
            image, geometry = self.parser.image_handle, self.parser.geometry
            assessments = assess_deleted_files(
                self.parser.evidence_objects,
                self.parser.allocation_ranges,
                self.parser.cluster_size,
                open_stream=lambda evidence: RunStream.for_evidence(image, geometry, evidence),
            )
            DeletedFileRepository(self.database).replace(self.case_id, assessments)
            return summarize_deleted(assessments), []
        except Exception as error:
            return {}, [
                f"Deleted-file assessment failed: {type(error).__name__}: {error}"
            ]

    def analyze_metafiles(self):
        """Parse NTFS metafiles and store their summary.

        A failure here is reported as a warning in the returned report and
        never fails the analysis.
        """
        try:
            report = MetafileAnalyzer(self.parser).analyze()
            MetafileRepository(self.database).replace(
                self.case_id, report.metafiles
            )
            return report
        except Exception as error:
            return MetafileReport(warnings=[
                f"Metafile analysis failed: {type(error).__name__}: {error}"
            ])
            

    def shutdown(self):

        if hasattr(self, "image") and self.image:

            self.image.close()

        if self.database:

            self.database.close()

    def run(
        self,
        image_path
    ):

        try:

            # Check before creating anything, so a bad path does not
            # leave an empty case behind in the database.
            if not os.path.isfile(image_path):
                raise FileNotFoundError(
                    f"Evidence image not found: {image_path}"
                )

            progress.report("Preparing case", force=True)

            self.initialize_case(
                image_path
            )

            self.initialize_case_database()

            progress.report("Locating NTFS volume", force=True)

            self.initialize_parser(
                image_path
            )

            self.analyze(
                image_path
            )

            self.result.case_id = self.case_id

            self.result.case_name = self.case.case_name

            self.result.investigator = self.case.investigator

            self.result.image_path = self.case.image_path

            self.repository.set_case_status(self.case_id, "complete")

            self.result.complete()

            progress.report("Analysis complete", 1, 1, force=True)

            return self.result

        except Exception as error:

            if self.repository is not None and self.case_id is not None:
                try:
                    self.repository.set_case_status(self.case_id, "failed")
                except Exception:
                    pass  # the original error is what matters

            self.result.failed(
                str(error)
            )

            return self.result

        finally:

            self.shutdown()