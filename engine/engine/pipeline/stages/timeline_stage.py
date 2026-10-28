from ..base_stage import PipelineStage

from ...timeline.timeline_event import TimelineEvent


class TimelineStage(PipelineStage):

    #
    # Timestamp → Event mapping
    #
    EVENT_MAPPING = (

        ("created_time", "Created"),

        ("modified_time", "Modified"),

        ("accessed_time", "Accessed"),

        ("mft_modified_time", "MFT Modified"),

    )

    def process(

        self,

        evidence_objects,

        context

    ):

        for evidence in evidence_objects:

            self._process_evidence(

                evidence,

                context

            )

    def _process_evidence(

        self,

        evidence,

        context

    ):

        #
        # Ignore records that never received
        # a reconstructed path.
        #
        if not evidence.full_path:

            return

        #
        # Generate one TimelineEvent
        # for every available timestamp.
        #
        for attribute, event_type in self.EVENT_MAPPING:

            timestamp = getattr(

                evidence,

                attribute,

                None

            )

            if timestamp is None:

                continue

            event = TimelineEvent(

                record_number=evidence.record_number,

                filename=evidence.filename,

                full_path=evidence.full_path,

                timestamp=timestamp,

                event_type=event_type,

                deleted=evidence.deleted,

                directory=evidence.directory,

            )

            context.timeline_events.append(

                event

            )