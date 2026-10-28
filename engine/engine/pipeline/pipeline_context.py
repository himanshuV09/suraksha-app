class PipelineContext:

    def __init__(

        self,

        image_reader,

        repository,

        case

    ):

        #
        # Shared pipeline resources
        #

        self.image_reader = image_reader

        self.repository = repository

        self.case = case

        #
        # Timeline
        #

        self.timeline_events = []

        #
        # Shared analysis cache
        #

        self.shared = {}