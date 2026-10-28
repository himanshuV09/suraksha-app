from collections import Counter

from database.mapper.timeline_mapper import TimelineMapper

from .timeline_aggregator import TimelineAggregator


class TimelineService:

    """
    Timeline business logic.

    Responsible for:

    • converting database rows into timeline events
    • aggregating timeline events for graph visualization
    • exposing raw forensic events
    • preparing investigation summaries
    """

    def __init__(self):

        self.aggregator = TimelineAggregator()

    def build(
        self,
        rows,
        interval="day",
    ):

        #
        # Convert database rows into TimelineEvent objects
        #

        events = TimelineMapper.to_object_list(
            rows
        )

        #
        # Build aggregated graph
        #

        graph = self.aggregator.aggregate(
            events,
            interval
        )

        #
        # Build raw forensic event list
        #

        event_list = [

            {
                "record_number": event.record_number,

                "timestamp": (
                    event.timestamp.isoformat()
                    if event.timestamp
                    else None
                ),

                "event_type": event.event_type,

                "filename": event.filename,

                "full_path": event.full_path,

                "source": event.source,

                "artifact_type": event.artifact_type,

                "deleted": bool(event.deleted),

                "directory": bool(event.directory),

                "description": event.description,

            }

            for event in events

        ]

        return {

            "summary": self._build_summary(
                events
            ),

            "graph": graph,

            "events": event_list,

        }

    # --------------------------------------------------
    # Summary
    # --------------------------------------------------

    def _build_summary(
        self,
        events,
    ):

        #
        # No events
        #

        if not events:

            return {

                "total_events": 0,

                "created": 0,

                "modified": 0,

                "accessed": 0,

                "deleted": 0,

                "mft_modified": 0,

                "first_event": None,

                "last_event": None,

                "most_active_day": None,

            }

        #
        # Count event types
        #

        counter = Counter(

            event.event_type

            for event in events

        )

        #
        # Ignore events without timestamps
        #

        dated_events = [

            event

            for event in events

            if event.timestamp is not None

        ]

        #
        # If events exist but none have timestamps
        #

        if not dated_events:

            return {

                "total_events": len(events),

                "created": counter["Created"],

                "modified": counter["Modified"],

                "accessed": counter["Accessed"],

                "deleted": counter["Deleted"],

                "mft_modified": counter["MFT Modified"],

                "first_event": None,

                "last_event": None,

                "most_active_day": None,

            }

        #
        # Extract timestamps
        #

        dates = [

            event.timestamp

            for event in dated_events

        ]

        #
        # Count events per day
        #

        daily_counter = Counter(

            dt.date()

            for dt in dates

        )

        #
        # Return summary
        #

        return {

            "total_events": len(events),

            "created": counter["Created"],

            "modified": counter["Modified"],

            "accessed": counter["Accessed"],

            "deleted": counter["Deleted"],

            "mft_modified": counter["MFT Modified"],

            "first_event":
                min(dates).isoformat(),

            "last_event":
                max(dates).isoformat(),

            "most_active_day":
                daily_counter
                .most_common(1)[0][0]
                .isoformat(),

        }