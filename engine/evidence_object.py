class EvidenceObject:

    def __init__(self):


        self.record_number = None
        self.parent_record = None
        self.parent_sequence_number = None

        self.filename = None
        self.full_path = None
        # Namespace rank of the $FILE_NAME chosen so far (see RecordProcessor).
        self.file_name_score = -1

        self.file_size = 0
        self.allocated_size = 0
        self.slack_space = 0
        self.slack_entropy = 0

        self.deleted = False
        self.directory = False
        self.record_type = ""

        self.mft_state = ""
        self.in_use = False
        self.sequence_number = None
        self.flags = 0
        self.used_size = 0
        self.record_allocated_size = 0

        self.created_time = None
        self.modified_time = None
        self.accessed_time = None
        self.mft_modified_time = None

        self.fragment_count = 0
        self.fragmented = False
        self.fragment_ratio = 0

        self.data_runs = []

        self.resident_data = None


        self.ads_streams = []

        self.timeline_events = []

        self.usn_events = []

        self.hashes = {}

        self.container_artifacts = []

        self.children = []

        self.risk_score = 0

        self.findings = []
