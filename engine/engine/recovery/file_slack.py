"""File slack: bytes between a file's end and the end of its clusters.

A file of 5,000 bytes on 4 KiB clusters occupies two clusters (8,192
bytes). The last 3,192 bytes are slack: NTFS does not clear them, so
they keep whatever was stored there before (fragments of deleted files).
Clusters allocated beyond that (pre-allocation) are slack too.
"""
import re

from engine.volume.run_stream import RunStream

MAX_SLACK_READ = 1024 * 1024
_PRINTABLE = re.compile(rb"[\x20-\x7e]{6,}")
_UTF16 = re.compile(rb"(?:[\x20-\x7e]\x00){6,}")


def slack_extent(evidence, cluster_size):
    """(start, end) byte offsets of the slack within the file's clusters."""
    if evidence.resident_data is not None or not evidence.data_runs:
        return None
    allocated = sum(
        run["length"] for run in evidence.data_runs if not run["sparse"]
    ) * cluster_size
    allocated = max(allocated, evidence.allocated_size or 0)
    start = evidence.file_size or 0
    if allocated <= start:
        return None
    return start, allocated


def read_slack(image, geometry, evidence, limit=MAX_SLACK_READ):
    """Raw slack bytes and the readable strings found in them."""
    extent = slack_extent(evidence, geometry.cluster_size)
    if extent is None:
        return {"slack_size": 0, "offset": None, "data": b"", "strings": []}

    start, end = extent
    total = sum(run["length"] for run in evidence.data_runs) * geometry.cluster_size
    # Read the raw clusters, ignoring the file's logical size.
    stream = RunStream(image, geometry, evidence.data_runs, total, total)
    data = stream.read_at(start, min(end - start, limit))

    strings = [match.group().decode("ascii") for match in _PRINTABLE.finditer(data)]
    strings += [match.group().decode("utf-16le") for match in _UTF16.finditer(data)]
    return {
        "slack_size": end - start,
        "offset": start,
        "data": data,
        "truncated": end - start > limit,
        "all_zero": not any(data),
        "strings": strings[:500],
    }
