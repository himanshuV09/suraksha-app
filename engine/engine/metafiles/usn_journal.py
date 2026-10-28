"""$Extend\\$UsnJrnl: the NTFS change journal.

Windows appends a record to the $J stream every time a file is created,
deleted, renamed, written, and so on. Each record names the file, its
parent directory and the reasons for the change, with a timestamp. It
survives the file itself, so it often shows deleted and renamed files
that the MFT no longer has.

$J is sparse: Windows frees its oldest part, so the stream starts with
a large zero region. Only non-sparse runs are read.

Record layout (USN_RECORD_V2; V3 widens the file references to 128 bits):

    0x00 RecordLength  u32      0x18 Usn            u64
    0x04 MajorVersion  u16      0x20 TimeStamp      FILETIME
    0x08 FileReference u64      0x28 Reason         u32
    0x10 ParentRef     u64      0x34 FileAttributes u32
    0x38 FileNameLength u16     0x3A FileNameOffset u16

Reference: forensicx core/timeline/UsnJournal.ts (record parser).
"""
import struct
from collections import Counter
from dataclasses import dataclass

from engine.metafiles.common import (
    ATTR_DATA,
    EXTEND_RECORD,
    filetime_to_datetime,
    is_plausible,
    mft_reference,
)
from engine.metafiles.i30 import find_child
from engine.metafiles.record import read_record_attributes
from engine.metafiles.stream import AttributeStream

USN_REASONS = {
    0x00000001: "DATA_OVERWRITE",
    0x00000002: "DATA_EXTEND",
    0x00000004: "DATA_TRUNCATION",
    0x00000010: "NAMED_DATA_OVERWRITE",
    0x00000020: "NAMED_DATA_EXTEND",
    0x00000040: "NAMED_DATA_TRUNCATION",
    0x00000100: "FILE_CREATE",
    0x00000200: "FILE_DELETE",
    0x00000400: "EA_CHANGE",
    0x00000800: "SECURITY_CHANGE",
    0x00001000: "RENAME_OLD_NAME",
    0x00002000: "RENAME_NEW_NAME",
    0x00004000: "INDEXABLE_CHANGE",
    0x00008000: "BASIC_INFO_CHANGE",
    0x00010000: "HARD_LINK_CHANGE",
    0x00020000: "COMPRESSION_CHANGE",
    0x00040000: "ENCRYPTION_CHANGE",
    0x00080000: "OBJECT_ID_CHANGE",
    0x00100000: "REPARSE_POINT_CHANGE",
    0x00200000: "STREAM_CHANGE",
    0x00400000: "TRANSACTED_CHANGE",
    0x00800000: "INTEGRITY_CHANGE",
    0x80000000: "CLOSE",
}

V2_MIN_LENGTH = 0x3C
V3_MIN_LENGTH = 0x4C
MAX_RECORD_LENGTH = 0x10000  # far above any real record (names <= 255 chars)


@dataclass(frozen=True)
class UsnRecord:
    usn: int
    timestamp: object  # datetime
    file_record: int
    file_sequence: int
    parent_record: int
    parent_sequence: int
    reason: int
    file_attributes: int
    name: str
    version: int

    @property
    def reasons(self):
        return [label for flag, label in USN_REASONS.items() if self.reason & flag]

    @property
    def action(self):
        """The single most significant change, for timeline display."""
        if self.reason & 0x00000200:
            return "Deleted"
        if self.reason & 0x00000100:
            return "Created"
        if self.reason & 0x00003000:
            return "Renamed"
        if self.reason & 0x00000007:
            return "Modified"
        return "Changed"

    @property
    def is_directory(self):
        return bool(self.file_attributes & 0x10)


def parse_usn_record(buffer, offset):
    """Decode one record at ``offset``; returns (record or None, length).

    A length of 0 means "no record here": the caller should step forward
    8 bytes (records are 8-byte aligned).
    """
    if offset + 8 > len(buffer):
        return None, 0

    length, major = struct.unpack_from("<IH", buffer, offset)
    if length == 0:
        return None, 0
    if major == 2:
        minimum = V2_MIN_LENGTH
    elif major == 3:
        minimum = V3_MIN_LENGTH
    else:
        return None, 0
    if length < minimum or length > MAX_RECORD_LENGTH or length % 8:
        return None, 0
    if offset + length > len(buffer):
        return None, length  # complete record needs more data

    if major == 2:
        file_ref, parent_ref, usn, timestamp, reason = struct.unpack_from(
            "<QQQQI", buffer, offset + 0x08
        )
        attributes, name_length, name_offset = struct.unpack_from(
            "<IHH", buffer, offset + 0x34
        )
    else:
        # 128-bit references; the low 64 bits hold record and sequence.
        file_ref = struct.unpack_from("<Q", buffer, offset + 0x08)[0]
        parent_ref = struct.unpack_from("<Q", buffer, offset + 0x18)[0]
        usn, timestamp, reason = struct.unpack_from("<QQI", buffer, offset + 0x28)
        attributes, name_length, name_offset = struct.unpack_from(
            "<IHH", buffer, offset + 0x44
        )

    if name_offset + name_length > length:
        return None, 0

    start = offset + name_offset
    name = bytes(buffer[start:start + name_length]).decode(
        "utf-16le", errors="replace"
    )
    file_record, file_sequence = mft_reference(file_ref)
    parent_record, parent_sequence = mft_reference(parent_ref)

    return UsnRecord(
        usn=usn,
        timestamp=filetime_to_datetime(timestamp),
        file_record=file_record,
        file_sequence=file_sequence,
        parent_record=parent_record,
        parent_sequence=parent_sequence,
        reason=reason,
        file_attributes=attributes,
        name=name,
        version=major,
    ), length


def iter_usn_records(segments):
    """Parse records from (offset, bytes, continues_previous) segments.

    A record split across two adjacent segments is joined; a sparse gap
    discards any partial record before it.
    """
    pending = b""
    for _, chunk, continues in segments:
        buffer = (pending + chunk) if continues else chunk
        pending = b""
        position = 0
        while position + 8 <= len(buffer):
            record, length = parse_usn_record(buffer, position)
            if record is not None:
                yield record
                position += length
            elif length:
                pending = buffer[position:]  # finish with the next segment
                break
            else:
                position += 8


@dataclass
class UsnJournal:
    record_number: int | None
    j_size: int = 0
    j_allocated_size: int = 0
    j_fragments: int = 0
    max_size: int | None = None
    allocation_delta: int | None = None
    journal_id: int | None = None
    lowest_valid_usn: int | None = None


def locate_usn_journal(parser):
    """Find $Extend\\$UsnJrnl and describe its streams; None if absent."""
    record_number = find_child(parser, EXTEND_RECORD, "$UsnJrnl")
    if record_number is None:
        return None, None

    record = read_record_attributes(parser, record_number)
    journal = UsnJournal(record_number=record_number)

    max_stream = record.find(ATTR_DATA, "$Max")
    if max_stream is not None:
        data = (
            max_stream.content if max_stream.resident
            else AttributeStream(parser.image, parser.geometry, max_stream).read_all(64)
        )
        if len(data) >= 32:
            (journal.max_size, journal.allocation_delta,
             journal.journal_id, journal.lowest_valid_usn) = struct.unpack_from("<QQQQ", data)

    j_stream = record.find(ATTR_DATA, "$J")
    if j_stream is not None:
        journal.j_size = j_stream.size
        journal.j_allocated_size = j_stream.allocated_size
        journal.j_fragments = j_stream.fragment_count

    return journal, j_stream


def summarize(records, limit):
    """Consume records into (kept records, summary dict)."""
    kept = []
    total = 0
    reasons = Counter()
    first = last = None
    for record in records:
        total += 1
        for label in record.reasons:
            reasons[label] += 1
        if is_plausible(record.timestamp):
            first = record.timestamp if first is None else min(first, record.timestamp)
            last = record.timestamp if last is None else max(last, record.timestamp)
        if len(kept) < limit:
            kept.append(record)
    return kept, {
        "record_count": total,
        "records_kept": len(kept),
        "truncated": total > len(kept),
        "first_timestamp": first,
        "last_timestamp": last,
        "reason_counts": dict(reasons.most_common()),
    }
