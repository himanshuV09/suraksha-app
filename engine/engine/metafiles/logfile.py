"""$LogFile: the NTFS transaction journal (MFT record 2).

The log starts with two restart pages ("RSTR") followed by log record
pages ("RCRD"). Each page is protected by an update sequence array,
exactly like an MFT record. The log records describe metadata changes;
their redo/undo data very often contain whole $FILE_NAME structures
(file creation, index insertions, renames).

Decoding every log operation is a research project. As in forensicx,
this module recovers the embedded $FILE_NAME structures instead: names,
parent directories and timestamps of recent metadata activity, which
frequently include files no longer present in the MFT.

Reference: forensicx core/timeline/LogFile.ts.
"""
import struct
from dataclasses import dataclass

from fixup import apply_fixup

from engine.metafiles.common import scan_file_names

RSTR = b"RSTR"
RCRD = b"RCRD"
CHKD = b"CHKD"  # restart page written by chkdsk
DEFAULT_PAGE_SIZE = 4096
RCRD_HEADER_SIZE = 0x40  # page header + update sequence array


@dataclass
class LogFileScan:
    page_size: int = DEFAULT_PAGE_SIZE
    log_page_size: int = DEFAULT_PAGE_SIZE
    restart_pages: int = 0
    record_pages: int = 0
    unreadable_pages: int = 0
    empty_pages: int = 0
    version: str | None = None
    current_lsn: int | None = None
    clean_dismount: bool | None = None
    entries: list = None  # [FileNameKey]
    truncated: bool = False

    def as_details(self):
        return {
            "page_size": self.page_size,
            "log_page_size": self.log_page_size,
            "current_lsn": self.current_lsn,
            # False means the volume was not cleanly unmounted (e.g. pulled
            # out, crash) and the log holds changes not yet checkpointed.
            "clean_dismount": self.clean_dismount,
            "restart_pages": self.restart_pages,
            "record_pages": self.record_pages,
            "unreadable_pages": self.unreadable_pages,
            "empty_pages": self.empty_pages,
            "log_version": self.version,
            "recovered_file_names": len(self.entries or []),
            "truncated": self.truncated,
        }


def read_restart_area(page):
    """(system_page_size, log_page_size, version) from a restart page."""
    if page[:4] not in (RSTR, CHKD) or len(page) < 0x1E:
        return None
    system_page_size, log_page_size, _, minor, major = struct.unpack_from(
        "<IIHhh", page, 0x10
    )
    valid = lambda size: 512 <= size <= 65536 and not size & (size - 1)
    if not (valid(system_page_size) and valid(log_page_size)):
        return None
    return system_page_size, log_page_size, f"{major}.{minor}"


RESTART_VOLUME_IS_CLEAN = 0x0002


def read_restart_state(page):
    """(current_lsn, clean_dismount) from a fixed-up restart page."""
    try:
        page = apply_fixup(page)
    except (ValueError, struct.error):
        return None, None
    restart_offset = struct.unpack_from("<H", page, 0x18)[0]
    if restart_offset < 0x1E or restart_offset + 0x10 > len(page):
        return None, None
    current_lsn, _, _, _, flags = struct.unpack_from("<QHHHH", page, restart_offset)
    return current_lsn, bool(flags & RESTART_VOLUME_IS_CLEAN)


def scan_logfile(stream, limit):
    """Read $LogFile page by page and recover embedded $FILE_NAMEs.

    ``limit`` caps how many distinct entries are kept.
    """
    result = LogFileScan(entries=[])
    first = stream.read(0, DEFAULT_PAGE_SIZE)
    restart = read_restart_area(first)
    if restart:
        result.page_size, result.log_page_size, result.version = restart
        # Two copies are kept; the one with the higher LSN is current.
        states = [
            read_restart_state(stream.read(offset, result.page_size))
            for offset in (0, result.page_size)
        ]
        states = [state for state in states if state[0] is not None]
        if states:
            result.current_lsn, result.clean_dismount = max(states)

    # Two restart pages of the system page size, then log pages.
    restart_area = 2 * result.page_size
    for offset in range(0, min(restart_area, stream.size), result.page_size):
        if stream.read(offset, 4) in (RSTR, CHKD):
            result.restart_pages += 1

    page_size = result.log_page_size
    seen = set()

    for offset in range(restart_area, stream.size - page_size + 1, page_size):
        page = stream.read(offset, page_size)
        signature = page[:4]

        if signature != RCRD:
            result.empty_pages += 1
            continue

        try:
            page = apply_fixup(page)
        except (ValueError, struct.error):
            result.unreadable_pages += 1
            continue

        result.record_pages += 1
        for _, key in scan_file_names(page, RCRD_HEADER_SIZE):
            identity = (key.name, key.parent_record, key.created, key.modified)
            if identity in seen:
                continue
            seen.add(identity)
            result.entries.append(key)
            if len(result.entries) >= limit:
                result.truncated = True
                return result

    return result
