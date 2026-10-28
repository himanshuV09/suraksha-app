from collections import defaultdict


class TimelineAggregator:

    """
    Aggregates TimelineEvent objects into
    chart-friendly datasets.

    This class contains no database code,
    no UI code and no API logic.
    """

    def aggregate(
        self,
        events,
        interval="day",
    ):

        interval = interval.lower()

        if interval == "day":
            return self.aggregate_daily(events)

        if interval == "week":
            return self.aggregate_weekly(events)

        if interval == "month":
            return self.aggregate_monthly(events)

        if interval == "year":
            return self.aggregate_yearly(events)

        raise ValueError(
            f"Unsupported interval: {interval}"
        )

    # --------------------------------------------------
    # Daily
    # --------------------------------------------------

    def aggregate_daily(
        self,
        events,
    ):

        buckets = defaultdict(
            self._empty_bucket
        )

        for event in events:

            if not event.has_timestamp:
                continue

            day = event.timestamp.date().isoformat()

            bucket = buckets[day]

            bucket["date"] = day

            self._increment(
                bucket,
                event.event_type
            )

        return self._sorted(
            buckets
        )

    # --------------------------------------------------
    # Weekly
    # --------------------------------------------------

    def aggregate_weekly(
        self,
        events,
    ):

        buckets = defaultdict(
            self._empty_bucket
        )

        for event in events:

            if not event.has_timestamp:
                continue

            year, week, _ = (
                event.timestamp.isocalendar()
            )

            key = f"{year}-W{week:02d}"

            bucket = buckets[key]

            bucket["date"] = key

            self._increment(
                bucket,
                event.event_type
            )

        return self._sorted(
            buckets
        )

    # --------------------------------------------------
    # Monthly
    # --------------------------------------------------

    def aggregate_monthly(
        self,
        events,
    ):

        buckets = defaultdict(
            self._empty_bucket
        )

        for event in events:

            if not event.has_timestamp:
                continue

            key = event.timestamp.strftime(
                "%Y-%m"
            )

            bucket = buckets[key]

            bucket["date"] = key

            self._increment(
                bucket,
                event.event_type
            )

        return self._sorted(
            buckets
        )

    # --------------------------------------------------
    # Yearly
    # --------------------------------------------------

    def aggregate_yearly(
        self,
        events,
    ):

        buckets = defaultdict(
            self._empty_bucket
        )

        for event in events:

            if not event.has_timestamp:
                continue

            key = str(
                event.timestamp.year
            )

            bucket = buckets[key]

            bucket["date"] = key

            self._increment(
                bucket,
                event.event_type
            )

        return self._sorted(
            buckets
        )

    # --------------------------------------------------
    # Helpers
    # --------------------------------------------------

    def _increment(
        self,
        bucket,
        event_type,
    ):

        mapping = {

            "Created": "created",

            "Modified": "modified",

            "Accessed": "accessed",

            "Deleted": "deleted",

            "MFT Modified": "mft_modified",

        }

        key = mapping.get(
            event_type
        )

        if key:
            bucket[key] += 1

    def _empty_bucket(self):

        return {

            "date": None,

            "created": 0,

            "modified": 0,

            "accessed": 0,

            "deleted": 0,

            "mft_modified": 0,

        }

    def _sorted(
        self,
        buckets,
    ):

        return sorted(

            buckets.values(),

            key=lambda bucket:
                bucket["date"]

        )