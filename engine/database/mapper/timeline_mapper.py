from engine.timeline.timeline_event import TimelineEvent

from datetime import datetime


class TimelineMapper:

    @staticmethod
    def to_object(row):

        return TimelineEvent(

            record_number=row[2],

            filename=row[3],

            full_path=row[4],

            timestamp=datetime.fromisoformat(row[5]),

            event_type=row[6],

            deleted=bool(row[7]),

            directory=bool(row[8]),

            source=row[9],

            artifact_type=row[10],

            description=row[11],

        )

    @classmethod
    def to_object_list(

        cls,

        rows

    ):

        return [

            cls.to_object(row)

            for row in rows

        ]