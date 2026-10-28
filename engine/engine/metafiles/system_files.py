"""Per-metafile summaries for the fixed NTFS system files (records 0-11).

Each function takes the parser and the metafile's parsed record and
returns a JSON-friendly ``details`` dict. They only read; nothing is
written to the image.
"""
import struct
from collections import Counter

from engine.metafiles.common import (
    ATTR_BITMAP,
    ATTR_DATA,
    ATTR_VOLUME_INFORMATION,
    ATTR_VOLUME_NAME,
    EXTEND_RECORD,
    ROOT_RECORD,
    WELL_KNOWN_SIDS,
    format_guid,
    format_sid,
)
from engine.metafiles.i30 import read_directory_index
from engine.metafiles.stream import AttributeStream
from engine.metafiles.view_index import read_view_index

ATTR_OBJECT_ID = 0x40

VOLUME_FLAGS = {
    0x0001: "DIRTY",
    0x0002: "RESIZE_LOG_FILE",
    0x0004: "UPGRADE_ON_MOUNT",
    0x0008: "MOUNTED_ON_NT4",
    0x0010: "DELETE_USN_UNDERWAY",
    0x0020: "REPAIR_OBJECT_ID",
    0x4000: "CHKDSK_UNDERWAY",
    0x8000: "MODIFIED_BY_CHKDSK",
}

ATTRDEF_ENTRY_SIZE = 0xA0
UPCASE_SIZE = 65536 * 2
SDS_BLOCK = 0x40000  # $SDS keeps each 256 KiB block followed by its mirror
MAX_SDS_READ = 64 * 1024 * 1024


def _stream(parser, attribute):
    return AttributeStream(parser.image, parser.geometry, attribute)


def _data(parser, record, name="", limit=None):
    attribute = record.find(ATTR_DATA, name)
    if attribute is None:
        return None
    return _stream(parser, attribute).read_all(limit)


def mft_details(parser, record):
    locator = parser.mft_locator
    details = {
        "record_size": parser.record_size,
        "record_count": parser.mft_record_count,
        "mft_size": parser.mft_size,
        "fragmented": bool(locator and locator.is_fragmented),
        "extents": len(locator.extents) if locator else None,
        "first_cluster": parser.ntfs_info["mft_cluster"],
        "extension_records": record.extension_records,
    }

    # $MFT:$BITMAP marks which MFT records are in use. Comparing it with
    # the in-use flags found while enumerating catches tampering/damage.
    bitmap = record.find(ATTR_BITMAP)
    if bitmap is not None:
        data = bitmap.content if bitmap.resident else _stream(parser, bitmap).read_all()
        count = parser.mft_record_count or 0
        # Only the first `count` bits describe existing records.
        bits = int.from_bytes(data[:(count + 7) // 8], "little") & ((1 << count) - 1)
        in_use = bin(bits).count("1")
        details["bitmap_records_in_use"] = in_use
        if parser.mft_slots:
            # Records whose header says "in use", found during enumeration.
            details["enumerated_records_in_use"] = parser.allocated_records
            details["bitmap_matches_records"] = in_use == parser.allocated_records

    return details


def mft_mirror_details(parser, record):
    """Compare the mirror's copies of the first MFT records with the MFT."""
    data = _data(parser, record, limit=64 * parser.record_size) or b""
    count = len(data) // parser.record_size
    mismatched = [
        number for number in range(count)
        if data[number * parser.record_size:(number + 1) * parser.record_size]
        != parser.read_record(number)
    ]
    return {
        "mirrored_records": count,
        "mirror_cluster": parser.ntfs_info.get("mft_mirror_cluster"),
        "matches_mft": not mismatched if count else None,
        "mismatched_records": mismatched,
    }


def volume_details(parser, record):
    details = {"label": None, "ntfs_version": None, "flags": [], "dirty": None}

    name = record.find(ATTR_VOLUME_NAME)
    if name is not None and name.resident:
        details["label"] = name.content.decode("utf-16le", errors="replace")

    info = record.find(ATTR_VOLUME_INFORMATION)
    if info is not None and info.resident and len(info.content) >= 12:
        major, minor, flags = struct.unpack_from("<BBH", info.content, 8)
        details["ntfs_version"] = f"{major}.{minor}"
        details["flags"] = [label for bit, label in VOLUME_FLAGS.items() if flags & bit]
        details["dirty"] = bool(flags & 0x0001)

    details["volume_object_id"] = _object_id(record)

    return details


def _object_id(record):
    attribute = record.find(ATTR_OBJECT_ID)
    if attribute is not None and attribute.resident:
        return format_guid(attribute.content)
    return None


def root_details(parser, record):
    index = read_directory_index(parser, ROOT_RECORD)
    return {
        "live_entries": sum(1 for entry in index.live if entry.key.namespace != 2),
        "deleted_entries_in_index": len(index.ghosts),
        "object_id": _object_id(record),
    }


def attrdef_details(parser, record):
    data = _data(parser, record, limit=64 * 1024) or b""
    definitions = []
    for offset in range(0, len(data) - ATTRDEF_ENTRY_SIZE + 1, ATTRDEF_ENTRY_SIZE):
        type_code = struct.unpack_from("<I", data, offset + 0x80)[0]
        if type_code == 0:
            break
        name = data[offset:offset + 0x80].decode("utf-16le", errors="replace").rstrip("\x00")
        definitions.append({"name": name, "type": hex(type_code)})
    return {"definition_count": len(definitions), "definitions": definitions}


def bitmap_details(parser, record):
    if not parser.allocation_ranges:
        parser.load_allocation()
    allocated = sum(
        item["cluster_count"] for item in parser.allocation_ranges
        if item["state"] == "allocated"
    )
    total = parser.total_clusters
    free = total - allocated
    return {
        "total_clusters": total,
        "allocated_clusters": allocated,
        "free_clusters": free,
        "free_bytes": free * parser.cluster_size,
        "free_percent": round(100 * free / total, 2) if total else None,
        "allocation_ranges": len(parser.allocation_ranges),
    }


def boot_details(parser, record):
    """Check the boot sector against its backup in the volume's last sector."""
    info = parser.ntfs_info
    sector = info["bytes_per_sector"]
    parser.image.seek(parser.volume_offset)
    primary = parser.image.read(sector)
    parser.image.seek(parser.volume_offset + info["total_sectors"] * sector)
    backup = parser.image.read(sector)
    return {
        "bytes_per_sector": sector,
        "sectors_per_cluster": info["sectors_per_cluster"],
        "total_sectors": info["total_sectors"],
        "serial_number": f"{info['serial_number']:016X}",
        "backup_available": len(backup) == sector,
        "backup_matches": (backup == primary) if len(backup) == sector else None,
    }


def badclus_details(parser, record):
    bad = record.find(ATTR_DATA, "$Bad")
    clusters = 0
    if bad is not None and not bad.resident:
        clusters = sum(run["length"] for run in bad.runs if not run["sparse"])
    return {"bad_clusters": clusters, "bad_bytes": clusters * parser.cluster_size}


def secure_details(parser, record):
    """Security descriptors in $Secure:$SDS, its two indexes, and owners."""
    data = _data(parser, record, "$SDS", limit=MAX_SDS_READ) or b""
    ids = set()
    owners = Counter()
    for block_start in range(0, len(data), 2 * SDS_BLOCK):
        position = block_start
        block_end = min(block_start + SDS_BLOCK, len(data))
        while position + 20 <= block_end:
            _, security_id, offset, length = struct.unpack_from("<IIQI", data, position)
            if length < 20 or offset != position or position + length > len(data):
                break
            ids.add(security_id)
            # Self-relative SECURITY_DESCRIPTOR follows the 20-byte header.
            descriptor = position + 20
            owner_offset = struct.unpack_from("<I", data, descriptor + 4)[0]
            if owner_offset:
                sid = format_sid(data[descriptor:position + length], owner_offset)
                if sid:
                    owners[sid] += 1
            position += (length + 15) & ~15

    sds = record.find(ATTR_DATA, "$SDS")
    return {
        "sds_size": sds.size if sds else 0,
        "security_descriptors": len(ids),
        "sii_entries": len(read_view_index(parser, record.record_number, "$SII", record)),
        "sdh_entries": len(read_view_index(parser, record.record_number, "$SDH", record)),
        "owners": [
            {"sid": sid, "account": WELL_KNOWN_SIDS.get(sid), "descriptors": count}
            for sid, count in owners.most_common(100)
        ],
    }


def upcase_details(parser, record):
    data = _data(parser, record, limit=UPCASE_SIZE) or b""
    valid = len(data) == UPCASE_SIZE and (
        struct.unpack_from("<H", data, ord("a") * 2)[0] == ord("A")
    )
    details = {"size": len(data), "valid": valid}

    # $UpCase:$Info (Windows 8+) records which Windows built the table,
    # i.e. which version formatted the volume.
    info = _data(parser, record, "$Info", limit=64) or b""
    if len(info) >= 32:
        _, _, crc, major, minor, build, pack_major, pack_minor = struct.unpack_from(
            "<IIQIIIHH", info
        )
        details["crc64"] = f"{crc:016X}"
        # Recent Windows versions leave the version fields zero.
        if major or build:
            details["formatted_by_windows"] = f"{major}.{minor} build {build}"
            details["service_pack"] = f"{pack_major}.{pack_minor}"
    return details


def extend_details(parser, record):
    index = read_directory_index(parser, EXTEND_RECORD, scan_slack=False)
    return {
        "children": sorted(
            ({"name": entry.key.name, "record_number": entry.file_record}
             for entry in index.live if entry.key.namespace != 2),
            key=lambda child: child["name"].lower(),
        ),
    }


DETAIL_PARSERS = {
    "$MFT": mft_details,
    "$MFTMirr": mft_mirror_details,
    "$Volume": volume_details,
    "$AttrDef": attrdef_details,
    ".": root_details,
    "$Bitmap": bitmap_details,
    "$Boot": boot_details,
    "$BadClus": badclus_details,
    "$Secure": secure_details,
    "$UpCase": upcase_details,
    "$Extend": extend_details,
}
