class Case:

    def __init__(self):

        self.case_name = ""
        self.image_path = ""
        self.created_at = None
        self.investigator = ""
        self.description = ""
        # "running" while being analyzed, then "complete" or "failed". A
        # case left "running" was interrupted (cancelled or crashed).
        self.status = "running"
        self.engine_version = ""
        self.evidence_count = 0
        self.timeline_count = 0
        self.graph_nodes = 0