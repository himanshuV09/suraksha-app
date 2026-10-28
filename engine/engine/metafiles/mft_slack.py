"""MFT record slack: names left behind in reused MFT records.

Each MFT record is a fixed 1 KiB (usually); only the first ``used_size``
bytes belong to the current file. When NTFS reuses a record for a new
file, the bytes after the new attributes are not cleared, so they often
still contain the previous file's $FILE_NAME attribute: its name, parent
directory and timestamps. That is evidence that the earlier file existed
even when nothing else remembers it.
"""
import struct
from dataclasses import dataclass

from fixup import apply_fixup

from engine.metafiles.common import scan_file_names

# $FILE_NAME content follows a 24-byte resident attribute header, so a
# leftover structure starts at least this far into the record.
MIN_OFFSET = 0x38


@dataclass(frozen=True)
class SlackEntry:
    record_number: int
    offset: int  # within the record
    key: object  # FileNameKey


def scan_record_slack(record_number, raw):
    """Old $FILE_NAME structures in the unused tail of one MFT record."""
    if len(raw) < 48 or raw[:4] != b"FILE":
        return []
    try:
        record = apply_fixup(raw)
    except ValueError:
        return []
    used_size = struct.unpack_from("<I", record, 24)[0]
    if not MIN_OFFSET <= used_size < len(record):
        return []
    # Live attributes end at used_size; anything after it is leftover.
    start = (used_size + 7) & ~7
    return [
        SlackEntry(record_number, offset, key)
        for offset, key in scan_file_names(record, start, len(record))
    ]


def scan_mft_slack(parser, live_names, limit):
    """Leftover names from every MFT record, minus names still current.

    ``live_names`` maps record number -> set of (lower-case name, parent)
    currently in that record, so a record's own name is not reported.
    Returns (entries, records_scanned, truncated).
    """
    entries = []
    scanned = 0
    for record_number in range(parser.mft_record_count or 0):
        raw = parser.read_record(record_number)
        scanned += 1
        current = live_names.get(record_number, set())
        seen = set()
        for entry in scan_record_slack(record_number, raw):
            identity = (entry.key.name.lower(), entry.key.parent_record)
            if identity in current or identity in seen:
                continue
            seen.add(identity)
            entries.append(entry)
            if len(entries) >= limit:
                return entries, scanned, True
    return entries, scanned, False
