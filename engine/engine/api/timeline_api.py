import sys

from database.case_database import Database
from database.repository import Repository

from engine.timeline.timeline_service import TimelineService


class TimelineAPI:

    def get_timeline(

        self,

        database_path: str,

        case_id: int,

        interval: str = "day",

        record_number: int | None = None,

    ):

        database = Database()

        try:

            #
            # Open case database
            #

            database.open_case(
                database_path
            )

            repository = Repository(
                database
            )

            #
            # Fetch timeline events
            #

            if record_number is None:

                print(
                    "Loading CASE timeline",
                    file=sys.stderr
                )

                rows = repository.get_timeline_events(
                    case_id
                )

            else:

                print(
                    f"Loading FILE timeline for record {record_number}",
                    file=sys.stderr
                )

                rows = repository.get_timeline_events_for_record(
                    case_id,
                    record_number,
                )

            print(
                f"Rows returned: {len(rows)}",
                file=sys.stderr
            )

            #
            # Build timeline
            #

            service = TimelineService()

            result = service.build(
                rows,
                interval
            )

            return {

                "success": True,

                "case_id": case_id,

                **result,

            }

        finally:

            database.close()