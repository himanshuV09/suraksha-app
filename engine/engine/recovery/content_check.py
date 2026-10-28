"""Check that a deleted file's bytes still look like its file type.

Metadata cannot always tell that a deleted file was overwritten: if the
data that overwrote it belonged to a file whose MFT record was itself
reused later, no trace of the overwrite remains. The content can still
tell: a ``.jpg`` must start with FF D8 FF, a ``.pdf`` with ``%PDF-``,
an Office document with ``PK`` and an end-of-archive record, and so on.

Only a few bytes at the start and end of each file are read.
"""
from dataclasses import dataclass

VERIFIED = "verified"          # start and end match the file type
HEADER_OK = "header_ok"        # start matches; the type has no end marker
MISMATCH = "mismatch"          # start or end does not match
UNKNOWN = "unknown"            # no rule for this file type

ZIP_TYPES = (
    ".zip", ".docx", ".xlsx", ".pptx", ".docm", ".xlsm", ".pptm", ".jar",
    ".apk", ".odt", ".ods", ".odp", ".epub", ".vsdx", ".xps",
)
OLE_TYPES = (".doc", ".xls", ".ppt", ".msg", ".vsd", ".pub")


@dataclass(frozen=True)
class TypeRule:
    header: bytes
    header_offset: int = 0
    trailer: bytes | None = None
    trailer_window: int = 1024  # the trailer must occur in the last N bytes


RULES = {
    # Phone cameras append trailers after the end marker (e.g. ~2 KB
    # watermark blocks), so allow 64 KiB after FF D9.
    ".jpg": TypeRule(b"\xff\xd8\xff", trailer=b"\xff\xd9", trailer_window=65536),
    ".png": TypeRule(b"\x89PNG\r\n\x1a\n", trailer=b"IEND", trailer_window=64),
    ".gif": TypeRule(b"GIF8", trailer=b"\x3b", trailer_window=16),
    ".pdf": TypeRule(b"%PDF-", trailer=b"%%EOF"),
    ".bmp": TypeRule(b"BM"),
    ".webp": TypeRule(b"WEBP", header_offset=8),
    ".tif": TypeRule(b"II*\x00"),
    ".exe": TypeRule(b"MZ"),
    ".e01": TypeRule(b"EVF\x09\x0d\x0a\xff\x00"),
    ".lnk": TypeRule(b"\x4c\x00\x00\x00\x01\x14\x02\x00"),
    ".mp4": TypeRule(b"ftyp", header_offset=4),
    ".mov": TypeRule(b"ftyp", header_offset=4),
    ".m4a": TypeRule(b"ftyp", header_offset=4),
    ".3gp": TypeRule(b"ftyp", header_offset=4),
    ".rar": TypeRule(b"Rar!\x1a\x07"),
    ".7z": TypeRule(b"7z\xbc\xaf\x27\x1c"),
    ".gz": TypeRule(b"\x1f\x8b\x08"),
    ".wav": TypeRule(b"WAVE", header_offset=8),
    ".avi": TypeRule(b"AVI ", header_offset=8),
    ".mkv": TypeRule(b"\x1a\x45\xdf\xa3"),
    ".sqlite": TypeRule(b"SQLite format 3\x00"),
    ".db": TypeRule(b"SQLite format 3\x00"),
}
for _ext in (".jpeg", ".jfif"):
    RULES[_ext] = RULES[".jpg"]
for _ext in (".dll", ".sys", ".scr"):
    RULES[_ext] = RULES[".exe"]
RULES[".tiff"] = RULES[".tif"]
for _ext in ZIP_TYPES:
    # End-of-central-directory record: within the last 22 + 65535 bytes.
    RULES[_ext] = TypeRule(b"PK\x03\x04", trailer=b"PK\x05\x06", trailer_window=65557)
for _ext in OLE_TYPES:
    RULES[_ext] = TypeRule(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")


def rule_for(filename):
    name = (filename or "").lower()
    dot = name.rfind(".")
    return RULES.get(name[dot:]) if dot >= 0 else None


def check_content(filename, file_size, read_at):
    """Return (result, header_ok, trailer_ok) for a file's bytes.

    ``read_at(offset, length)`` reads from the file's own data stream.
    """
    rule = rule_for(filename)
    if rule is None or file_size < rule.header_offset + len(rule.header):
        return UNKNOWN, None, None

    header = read_at(rule.header_offset, len(rule.header))
    header_ok = header == rule.header

    if rule.trailer is None:
        return (HEADER_OK if header_ok else MISMATCH), header_ok, None

    window = min(file_size, rule.trailer_window)
    trailer_ok = rule.trailer in read_at(file_size - window, window)
    result = VERIFIED if header_ok and trailer_ok else MISMATCH
    return result, header_ok, trailer_ok
