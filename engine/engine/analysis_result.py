from datetime import datetime


class AnalysisResult:

    def __init__(self):

        # Analysis Status
        self.success = False
        self.message = ""

        # Case Information
        self.case_id = None
        self.case_name = ""
        self.investigator = ""
        self.image_path = ""
        # Absolute path of the case database. Clients must use this
        # value for follow-up commands instead of guessing it.
        self.database_path = ""

        # Filesystem Information
        self.filesystem = ""
        self.volume_label = ""
        self.serial_number = ""

        # Image Information
        self.image_size = 0
        self.cluster_size = 0
        self.sector_size = 0

        # Record Statistics
        self.total_records = 0
        self.total_files = 0
        self.total_directories = 0
        self.deleted_files = 0

        # Advanced Statistics
        self.fragmented_files = 0
        self.fragment_count = 0

        self.ads_files = 0

        self.slack_files = 0

        self.high_risk_files = 0

        self.timeline_events = 0

        # Parsing health. Malformed MFT records are skipped, not fatal;
        # these fields say how many were skipped and why.
        self.corrupt_records = 0
        self.record_error_count = 0
        self.record_errors = []  # first N: {"record_number", "error"}
        self.warnings = []

        # NTFS metafile results: usn_records, logfile_entries,
        # i30_ghost_entries, metafiles, ... (see MetafileAnalyzer).
        self.metafile_counts = {}

        # Deleted files graded against $Bitmap: deleted_recoverable,
        # deleted_partial, deleted_overwritten, deleted_recoverable_bytes...
        self.deleted_recovery = {}

        # Timing
        self.started_at = datetime.now()
        self.completed_at = None
        self.duration = 0

        # Errors
        self.errors = []

    def add_error(
        self,
        message
    ):
        self.errors.append(message)

    def complete(self):

        self.success = True

        self.completed_at = datetime.now()

        self.duration = (
            self.completed_at
            -
            self.started_at
        ).total_seconds()

    def failed(
        self,
        message
    ):

        self.success = False

        self.add_error(message)

        self.completed_at = datetime.now()

        self.duration = (
            self.completed_at
            -
            self.started_at
        ).total_seconds()

    def to_dictionary(self):

        return {

            "success": self.success,

            "message": self.message,

            "case_id": self.case_id,

            "case_name": self.case_name,

            "investigator": self.investigator,

            "image_path": self.image_path,

            "database_path": self.database_path,

            "filesystem": self.filesystem,

            "volume_label": self.volume_label,

            "serial_number": self.serial_number,

            "image_size": self.image_size,

            "cluster_size": self.cluster_size,

            "sector_size": self.sector_size,

            "total_records": self.total_records,

            "total_files": self.total_files,

            "total_directories": self.total_directories,

            "deleted_files": self.deleted_files,

            "fragmented_files": self.fragmented_files,

            "fragment_count": self.fragment_count,

            "ads_files": self.ads_files,

            "slack_files": self.slack_files,

            "high_risk_files": self.high_risk_files,

            "timeline_events": self.timeline_events,

            "corrupt_records": self.corrupt_records,

            "record_error_count": self.record_error_count,

            "record_errors": self.record_errors,

            "warnings": self.warnings,

            "metafile_counts": self.metafile_counts,

            "deleted_recovery": self.deleted_recovery,

            "duration": self.duration,

            "errors": self.errors
        }