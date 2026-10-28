"""Grade deleted files by whether their data is still on disk.

When NTFS deletes a file it clears the "in use" flag of its MFT record
and marks its clusters free in $Bitmap, but leaves the record (name,
parent, timestamps, data runs) and the data itself in place until they
are reused. So a deleted file is:

    recoverable  none of its clusters were reused: data is intact
    partial      some clusters were reused by other data
    overwritten  every cluster was reused
    no_data      it had no content (empty file)

A cluster counts as reused when either

  * $Bitmap marks it allocated (a live file or metadata now uses it), or
  * another deleted file that was written later also claims it.

The second case matters: if file A is deleted, file B is written over
A's clusters and then B is deleted too, $Bitmap shows those clusters as
free again, yet they hold B's data. Checking $Bitmap alone (as forensicx
recoverDeleted does) reports A as intact. On a real test volume this
mis-graded 73 of 177 deleted files.

Small files whose content is stored inside the MFT record ("resident")
are recoverable as long as the record itself is readable.
"""
from bisect import bisect_right
from dataclasses import asdict, dataclass, field

from engine.recovery.content_check import MISMATCH, UNKNOWN, check_content

RECOVERABLE = "recoverable"
PARTIAL = "partial"
OVERWRITTEN = "overwritten"
NO_DATA = "no_data"

MAX_OWNERS_LISTED = 5


@dataclass
class DeletedFileAssessment:
    record_number: int
    sequence_number: int | None
    filename: str
    full_path: str
    file_size: int
    resident: bool
    status: str
    total_clusters: int = 0
    free_clusters: int = 0
    reused_clusters: int = 0
    recoverable_bytes: int = 0
    # Files that now hold some of this file's old clusters.
    overwritten_by: list = field(default_factory=list)
    # [start, end) byte offsets of the file that hold other data now.
    unreliable_ranges: list = field(default_factory=list)
    # Do the bytes still look like the file type? See content_check.py.
    content_check: str = UNKNOWN
    created: object = None
    modified: object = None
    accessed: object = None
    mft_modified: object = None

    @property
    def recoverable_percent(self):
        if not self.file_size:
            return 100.0 if self.status == RECOVERABLE else 0.0
        return round(100 * self.recoverable_bytes / self.file_size, 1)

    def to_dictionary(self):
        data = asdict(self)
        data["recoverable_percent"] = self.recoverable_percent
        return data


# ----------------------------------------------------------------------
# Interval helpers (half-open [start, end) cluster ranges)
# ----------------------------------------------------------------------

def _merge(intervals):
    merged = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged


def _clip(intervals, start, end):
    return [(max(a, start), min(b, end)) for a, b in intervals if a < end and b > start]


class ClusterAllocation:
    """Allocated cluster ranges from $Bitmap, queried by range."""

    def __init__(self, allocation_ranges):
        self.ranges = sorted(
            (item["start_cluster"], item["end_cluster"] + 1)
            for item in allocation_ranges if item["state"] == "allocated"
        )
        self.starts = [start for start, _ in self.ranges]

    def allocated_intervals(self, start, length):
        end = start + length
        found = []
        index = max(0, bisect_right(self.starts, start) - 1)
        while index < len(self.ranges) and self.ranges[index][0] < end:
            a, b = self.ranges[index]
            if b > start:
                found.append((max(a, start), min(b, end)))
            index += 1
        return found

    def allocated_in(self, start, length):
        return sum(b - a for a, b in self.allocated_intervals(start, length))


class ClusterOwners:
    """Which live file owns a cluster range (live files never overlap)."""

    def __init__(self, live_files):
        intervals = []
        for evidence in live_files:
            for run in evidence.data_runs or []:
                if not run["sparse"] and run["length"] > 0:
                    intervals.append((run["lcn"], run["lcn"] + run["length"], evidence))
        intervals.sort(key=lambda item: item[0])
        self.intervals = intervals
        self.starts = [item[0] for item in intervals]

    def owners_of(self, start, length):
        end = start + length
        owners = []
        index = max(0, bisect_right(self.starts, start) - 1)
        while index < len(self.intervals) and self.intervals[index][0] < end:
            if self.intervals[index][1] > start:
                owners.append(self.intervals[index][2])
            index += 1
        return owners


def _content_runs(evidence, cluster_size):
    """(file_offset, lcn, clusters) for the clusters holding real content."""
    remaining = evidence.file_size or 0
    offset = 0
    for run in evidence.data_runs or []:
        if remaining <= 0:
            break  # clusters past the end of the file are slack
        run_bytes = run["length"] * cluster_size
        if not run["sparse"]:
            used = min(run["length"], -(-remaining // cluster_size))
            yield offset, run["lcn"], used
        offset += run_bytes
        remaining -= run_bytes


def _write_time(evidence):
    """When this file's data was last written to the volume, if known.

    Windows keeps the original modified time when copying a file, so the
    created time marks when a copy arrived; the later of the two is the
    best available estimate.
    """
    times = [t for t in (evidence.created_time, evidence.modified_time) if t is not None]
    return max(times) if times else None


def superseded_clusters(deleted_files, cluster_size):
    """Cluster ranges each deleted file lost to a later-written deleted file.

    Returns {record_number: ([[start, end), ...], [names of newer files])}.
    """
    intervals = []
    for evidence in deleted_files:
        for _, lcn, used in _content_runs(evidence, cluster_size):
            intervals.append((lcn, lcn + used, evidence))
    intervals.sort(key=lambda item: item[0])

    lost = {}
    active = []  # intervals that may still overlap later ones
    for start, end, evidence in intervals:
        active = [item for item in active if item[1] > start]
        for other_start, other_end, other in active:
            if other is evidence:
                continue
            overlap = (start, min(end, other_end))
            mine, theirs = _write_time(evidence), _write_time(other)
            if mine is not None and theirs is not None and mine != theirs:
                losers = [(evidence, other)] if mine < theirs else [(other, evidence)]
            else:
                losers = [(evidence, other), (other, evidence)]  # order unknown
            for loser, winner in losers:
                ranges, names = lost.setdefault(loser.record_number, ([], []))
                ranges.append(overlap)
                name = f"{winner.full_path or winner.filename} (deleted)"
                if name not in names:
                    names.append(name)
        active.append((start, end, evidence))

    return {
        record: (_merge(ranges), names) for record, (ranges, names) in lost.items()
    }


# ----------------------------------------------------------------------
# Assessment
# ----------------------------------------------------------------------

def assess_deleted_files(evidence_objects, allocation_ranges, cluster_size, open_stream=None):
    """One assessment per deleted (non-directory) file, in record order.

    ``open_stream(evidence)`` returns a seekable stream over the file's
    data; when given, each file's content is also checked against its
    file type (catching overwrites that left no metadata trace).
    """
    allocation = ClusterAllocation(allocation_ranges)
    owners = ClusterOwners(e for e in evidence_objects if not e.deleted)
    deleted = [e for e in evidence_objects if e.deleted and not e.directory]
    superseded = superseded_clusters(
        [e for e in deleted if e.resident_data is None], cluster_size
    )

    return [
        assess(evidence, allocation, owners, cluster_size,
               superseded.get(evidence.record_number, ([], [])), open_stream)
        for evidence in deleted
    ]


def assess(evidence, allocation, owners, cluster_size, superseded=([], []), open_stream=None):
    result = DeletedFileAssessment(
        record_number=evidence.record_number,
        sequence_number=evidence.sequence_number,
        filename=evidence.filename or f"[record {evidence.record_number}]",
        full_path=evidence.full_path or evidence.filename or "",
        file_size=evidence.file_size or 0,
        resident=evidence.resident_data is not None,
        status=NO_DATA,
        created=evidence.created_time,
        modified=evidence.modified_time,
        accessed=evidence.accessed_time,
        mft_modified=evidence.mft_modified_time,
    )

    if result.resident:
        # Content lives inside the MFT record itself.
        result.status = RECOVERABLE if result.file_size else NO_DATA
        result.recoverable_bytes = len(evidence.resident_data)
        data = evidence.resident_data
        result.content_check = check_content(
            result.filename, len(data), lambda offset, length: data[offset:offset + length]
        )[0]
        return result

    if not result.file_size or not evidence.data_runs:
        return result

    superseded_ranges, superseded_names = superseded
    reused_names = []
    unreliable = []

    for file_offset, lcn, used in _content_runs(evidence, cluster_size):
        end = lcn + used
        allocated = allocation.allocated_intervals(lcn, used)
        lost = _merge(allocated + _clip(superseded_ranges, lcn, end))
        lost_clusters = sum(b - a for a, b in lost)

        result.total_clusters += used
        result.reused_clusters += lost_clusters
        result.free_clusters += used - lost_clusters

        for a, b in lost:
            start = file_offset + (a - lcn) * cluster_size
            stop = min(file_offset + (b - lcn) * cluster_size, result.file_size)
            if unreliable and unreliable[-1][1] == start:
                unreliable[-1][1] = stop
            else:
                unreliable.append([start, stop])

        for a, b in allocated:
            for owner in owners.owners_of(a, b - a):
                name = owner.full_path or owner.filename
                if name not in reused_names:
                    reused_names.append(name)

    for name in superseded_names:
        if name not in reused_names:
            reused_names.append(name)

    lost_bytes = sum(b - a for a, b in unreliable)
    if open_stream is not None and lost_bytes < result.file_size:
        unreliable = _check_content(result, evidence, open_stream, unreliable, cluster_size)
        lost_bytes = sum(b - a for a, b in unreliable)

    result.recoverable_bytes = max(0, result.file_size - lost_bytes)
    result.unreliable_ranges = unreliable
    result.overwritten_by = reused_names[:MAX_OWNERS_LISTED]

    if lost_bytes == 0:
        result.status = RECOVERABLE
    elif lost_bytes >= result.file_size:
        result.status = OVERWRITTEN
    else:
        result.status = PARTIAL

    # Cluster counts that agree with the byte ranges, content check included.
    result.reused_clusters = min(result.total_clusters, sum(
        -(-b // cluster_size) - a // cluster_size for a, b in unreliable
    ))
    result.free_clusters = result.total_clusters - result.reused_clusters

    return result


def _check_content(result, evidence, open_stream, unreliable, cluster_size):
    """Mark the first/last cluster unreliable if the bytes fail the type check."""
    stream = open_stream(evidence)
    check, header_ok, trailer_ok = check_content(
        result.filename, result.file_size, stream.read_at
    )
    result.content_check = check
    if check != MISMATCH:
        return unreliable

    extra = []
    if header_ok is False:
        extra.append((0, min(cluster_size, result.file_size)))
    if trailer_ok is False:
        last_cluster = (result.file_size - 1) // cluster_size * cluster_size
        extra.append((last_cluster, result.file_size))
    return _merge([tuple(r) for r in unreliable] + extra)


def summarize(assessments):
    counts = {RECOVERABLE: 0, PARTIAL: 0, OVERWRITTEN: 0, NO_DATA: 0}
    for item in assessments:
        counts[item.status] += 1
    return {
        "deleted_files": len(assessments),
        "deleted_recoverable": counts[RECOVERABLE],
        "deleted_partial": counts[PARTIAL],
        "deleted_overwritten": counts[OVERWRITTEN],
        "deleted_no_data": counts[NO_DATA],
        "deleted_recoverable_bytes": sum(item.recoverable_bytes for item in assessments),
    }
