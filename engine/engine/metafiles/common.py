"""Shared constants and decoders for NTFS metafile parsing."""
import struct
from dataclasses import dataclass
from datetime import datetime, timedelta

# Fixed MFT record numbers of the NTFS system metafiles.
SYSTEM_RECORDS = {
    "$MFT": 0,
    "$MFTMirr": 1,
    "$LogFile": 2,
    "$Volume": 3,
    "$AttrDef": 4,
    ".": 5,
    "$Bitmap": 6,
    "$Boot": 7,
    "$BadClus": 8,
    "$Secure": 9,
    "$UpCase": 10,
    "$Extend": 11,
}

EXTEND_RECORD = SYSTEM_RECORDS["$Extend"]
ROOT_RECORD = SYSTEM_RECORDS["."]

# Attribute type codes used by the metafile parsers.
ATTR_STANDARD_INFORMATION = 0x10
ATTR_ATTRIBUTE_LIST = 0x20
ATTR_FILE_NAME = 0x30
ATTR_VOLUME_NAME = 0x60
ATTR_VOLUME_INFORMATION = 0x70
ATTR_DATA = 0x80
ATTR_INDEX_ROOT = 0x90
ATTR_INDEX_ALLOCATION = 0xA0
ATTR_BITMAP = 0xB0

FILETIME_EPOCH = datetime(1601, 1, 1)

# Timestamps outside this range are treated as garbage when carving
# structures out of slack or journals (same bounds as forensicx).
PLAUSIBLE_YEARS = (1980, 2100)

FILE_NAME_HEADER_SIZE = 0x42

# $FILE_NAME namespaces. Win32 names are what users see; DOS names are
# the generated 8.3 aliases.
NAMESPACE_POSIX = 0
NAMESPACE_WIN32 = 1
NAMESPACE_DOS = 2
NAMESPACE_WIN32_AND_DOS = 3


def filetime_to_datetime(value):
    """Convert a Windows FILETIME; 0 and out-of-range values become None."""
    if not value:
        return None
    try:
        return FILETIME_EPOCH + timedelta(microseconds=value // 10)
    except OverflowError:
        return None


def is_plausible(timestamp):
    return (
        timestamp is not None
        and PLAUSIBLE_YEARS[0] <= timestamp.year <= PLAUSIBLE_YEARS[1]
    )


def mft_reference(value):
    """Split a 64-bit MFT reference into (record_number, sequence)."""
    return value & 0x0000FFFFFFFFFFFF, value >> 48


def format_guid(data):
    """A Windows GUID (16 bytes, mixed endian) as text; None if absent."""
    if len(data) < 16 or not any(data[:16]):
        return None
    a, b, c = struct.unpack_from("<IHH", data)
    return f"{a:08X}-{b:04X}-{c:04X}-{data[8:10].hex().upper()}-{data[10:16].hex().upper()}"


def format_sid(data, offset=0):
    """A Windows security identifier as "S-1-5-21-..."; None if invalid."""
    if offset + 8 > len(data):
        return None
    revision, count = data[offset], data[offset + 1]
    if revision != 1 or count > 15 or offset + 8 + 4 * count > len(data):
        return None
    authority = int.from_bytes(data[offset + 2:offset + 8], "big")
    parts = struct.unpack_from(f"<{count}I", data, offset + 8)
    return "-".join(["S", str(revision), str(authority), *map(str, parts)])


# Well-known accounts, to make owner lists readable.
WELL_KNOWN_SIDS = {
    "S-1-1-0": "Everyone",
    "S-1-3-0": "CREATOR OWNER",
    "S-1-5-18": "SYSTEM",
    "S-1-5-19": "LOCAL SERVICE",
    "S-1-5-20": "NETWORK SERVICE",
    "S-1-5-32-544": "BUILTIN\\Administrators",
    "S-1-5-32-545": "BUILTIN\\Users",
    "S-1-5-11": "Authenticated Users",
}


@dataclass(frozen=True)
class FileNameKey:
    """A $FILE_NAME structure, as stored in MFT records, indexes and logs."""

    name: str
    parent_record: int
    parent_sequence: int
    created: datetime | None
    modified: datetime | None
    mft_modified: datetime | None
    accessed: datetime | None
    allocated_size: int
    real_size: int
    flags: int
    namespace: int

    @property
    def length(self):
        return FILE_NAME_HEADER_SIZE + 2 * len(self.name)

    @property
    def is_directory(self):
        return bool(self.flags & 0x10000000)


def decode_file_name(buffer, offset, require_plausible=False):
    """Decode a $FILE_NAME structure at ``offset``; None if it is not one.

    ``require_plausible`` applies the checks used when carving from slack
    or journals: sane timestamps, namespace, and printable name.
    """
    if offset < 0 or offset + FILE_NAME_HEADER_SIZE > len(buffer):
        return None

    name_length = buffer[offset + 0x40]
    namespace = buffer[offset + 0x41]
    name_end = offset + FILE_NAME_HEADER_SIZE + 2 * name_length

    if name_length == 0 or namespace > 3 or name_end > len(buffer):
        return None

    parent_reference, created, modified, mft_modified, accessed = (
        struct.unpack_from("<QQQQQ", buffer, offset)
    )
    allocated_size, real_size, flags = struct.unpack_from(
        "<QQI", buffer, offset + 0x28
    )

    created = filetime_to_datetime(created)
    modified = filetime_to_datetime(modified)

    name = bytes(buffer[offset + FILE_NAME_HEADER_SIZE:name_end]).decode(
        "utf-16le", errors="replace"
    )

    if require_plausible:
        if not (is_plausible(created) and is_plausible(modified)):
            return None
        if any(ord(char) < 0x20 or char in "\x7f�" for char in name):
            return None

    parent_record, parent_sequence = mft_reference(parent_reference)

    return FileNameKey(
        name=name,
        parent_record=parent_record,
        parent_sequence=parent_sequence,
        created=created,
        modified=modified,
        mft_modified=filetime_to_datetime(mft_modified),
        accessed=filetime_to_datetime(accessed),
        allocated_size=allocated_size,
        real_size=real_size,
        flags=flags,
        namespace=namespace,
    )


def scan_file_names(buffer, start=0, end=None, step=8):
    """Find plausible $FILE_NAME structures anywhere in a byte range.

    Used for slack and journal pages, where structures are not reachable
    through any header. NTFS keeps them 8-byte aligned.
    """
    end = len(buffer) if end is None else min(end, len(buffer))
    found = []
    offset = start
    while offset + FILE_NAME_HEADER_SIZE <= end:
        key = decode_file_name(buffer, offset, require_plausible=True)
        if key is not None and offset + key.length <= end:
            found.append((offset, key))
            # Continue after this structure: the same bytes read 8 bytes
            # later can also look plausible (shifted fields, cut-off name).
            offset += (key.length + step - 1) // step * step
            continue
        offset += step
    return found
