"""Encoders for NTFS metafile structures, for building test images.

Each function returns the exact bytes NTFS stores on disk.
"""
import struct

from support.ntfs_image import (
    DEFAULT_FILETIME,
    SECTOR_SIZE,
    _align,
    _apply_update_sequence,
)

ONE_HOUR = 36_000_000_000  # in FILETIME units (100 ns)


def file_name(name, parent, parent_sequence=5, filetime=DEFAULT_FILETIME,
              directory=False, namespace=1, size=0):
    """$FILE_NAME content (as in MFT records, index keys and logs)."""
    encoded = name.encode("utf-16le")
    content = bytearray(0x42 + len(encoded))
    struct.pack_into("<Q", content, 0, parent | (parent_sequence << 48))
    struct.pack_into("<QQQQ", content, 8, filetime, filetime + ONE_HOUR, filetime, filetime)
    struct.pack_into("<QQ", content, 0x28, _align(size, 8), size)
    struct.pack_into("<I", content, 0x38, 0x10000000 if directory else 0x20)
    content[0x40] = len(name)
    content[0x41] = namespace
    content[0x42:] = encoded
    return bytes(content)


def index_entry(record, key, sequence=1):
    length = _align(0x10 + len(key), 8)
    entry = bytearray(length)
    struct.pack_into("<QHHH", entry, 0, record | (sequence << 48), length, len(key), 0)
    entry[0x10:0x10 + len(key)] = key
    return bytes(entry)


def index_root(entries, slack=b""):
    """$INDEX_ROOT ($I30) content: live entries, end entry, then slack.

    ``entries`` are (record, key) pairs. ``slack`` sits after the "used"
    end of the node, where deleted entries linger.
    """
    body = b"".join(index_entry(record, key) for record, key in entries)
    body += struct.pack("<QHHH", 0, 0x10, 0, 0x02) + bytes(2)  # end entry
    used = 0x10 + len(body)
    allocated = used + len(slack)

    header = struct.pack("<IIIB", 0x30, 1, 4096, 1) + bytes(3)
    node = struct.pack("<IIIB", 0x10, used, allocated, 0) + bytes(3)
    return header + node + body + slack


def usn_record(usn, file_record, parent, name, reason, filetime=DEFAULT_FILETIME,
               attributes=0x20):
    """One USN_RECORD_V2."""
    encoded = name.encode("utf-16le")
    length = _align(0x3C + len(encoded), 8)
    record = bytearray(length)
    struct.pack_into("<IHH", record, 0, length, 2, 0)
    struct.pack_into("<QQQQI", record, 8, file_record | (1 << 48),
                     parent | (5 << 48), usn, filetime, reason)
    struct.pack_into("<IHH", record, 0x34, attributes, len(encoded), 0x3C)
    record[0x3C:0x3C + len(encoded)] = encoded
    return bytes(record)


def usn_max(max_size=32 * 1024 * 1024, delta=4 * 1024 * 1024, journal_id=0x1D9, lowest=0):
    return struct.pack("<QQQQ", max_size, delta, journal_id, lowest)


def logfile(file_names, page_size=4096, record_pages=1, lsn=0x1234, clean=True):
    """A $LogFile: two RSTR pages, then RCRD pages holding $FILE_NAMEs.

    The second restart page carries the newer LSN, as NTFS alternates.
    """
    usa_count = page_size // SECTOR_SIZE + 1

    def restart_page(current_lsn):
        page = bytearray(page_size)
        page[0:4] = b"RSTR"
        struct.pack_into("<HH", page, 4, 0x1E, usa_count)
        struct.pack_into("<IIHhh", page, 0x10, page_size, page_size, 0x30, 1, 1)
        # Restart area: current LSN, clients, flags (0x0002 = clean).
        struct.pack_into("<QHHHH", page, 0x30, current_lsn, 1, 0xFFFF, 0, 0x0002 if clean else 0)
        return _apply_update_sequence(page, 0x1E, usa_count)

    def record_page(names):
        page = bytearray(page_size)
        page[0:4] = b"RCRD"
        struct.pack_into("<HH", page, 4, 0x28, usa_count)
        offset = 0x48
        for name in names:
            page[offset:offset + len(name)] = name
            offset = _align(offset + len(name) + 0x18, 8)
        return _apply_update_sequence(page, 0x28, usa_count)

    pages = [restart_page(lsn - 1), restart_page(lsn), record_page(file_names)]
    pages += [bytes(page_size)] * (record_pages - 1)
    return b"".join(pages)


def volume_information(major=3, minor=1, flags=0):
    return bytes(8) + struct.pack("<BBH", major, minor, flags) + bytes(4)


# ---------------------------------------------------------------------
# View indexes ($ObjId:$O, $Reparse:$R, $Quota:$O/$Q, $Secure:$SII)
# ---------------------------------------------------------------------

def view_entry(key, data=b""):
    data_offset = _align(0x10 + len(key), 8)
    length = _align(data_offset + len(data), 8)
    entry = bytearray(length)
    struct.pack_into(
        "<HHIHHH", entry, 0,
        data_offset if data else 0, len(data), 0, length, len(key), 0,
    )
    entry[0x10:0x10 + len(key)] = key
    entry[data_offset:data_offset + len(data)] = data
    return bytes(entry)


def view_index_root(entries, collation=0x10):
    """$INDEX_ROOT content of a view index with (key, data) entries."""
    body = b"".join(view_entry(key, data) for key, data in entries)
    body += struct.pack("<HHIHHHH", 0, 0, 0, 0x10, 0, 0x02, 0)  # last entry
    used = 0x10 + len(body)
    header = struct.pack("<IIIB", 0, collation, 4096, 1) + bytes(3)
    node = struct.pack("<IIIB", 0x10, used, used, 0) + bytes(3)
    return header + node + body


def guid(text):
    """GUID text -> 16 bytes in Windows (mixed-endian) order."""
    import uuid
    return uuid.UUID(text).bytes_le


def sid(*sub_authorities, authority=5):
    return (
        bytes([1, len(sub_authorities)])
        + authority.to_bytes(6, "big")
        + struct.pack(f"<{len(sub_authorities)}I", *sub_authorities)
    )


def sds_entry(security_id, owner_sid, offset):
    """One $Secure:$SDS entry: header + self-relative descriptor."""
    descriptor = struct.pack("<BBHIIII", 1, 0, 0x8004, 20, 0, 0, 0) + owner_sid
    length = 20 + len(descriptor)
    return struct.pack("<IIQI", 0xABCD, security_id, offset, length) + descriptor


def quota_entry(bytes_used, owner_sid=b""):
    return struct.pack("<IIQQqqQ", 2, 0, bytes_used, DEFAULT_FILETIME, -1, -1, 0) + owner_sid


def upcase_table():
    table = list(range(65536))
    for char in range(ord("a"), ord("z") + 1):
        table[char] = char - 32
    return struct.pack("<65536H", *table)


def upcase_info(major=10, minor=0, build=19041):
    return struct.pack("<IIQIIIHH", 32, 0, 0x1122334455667788, major, minor, build, 0, 0)
