"""Summaries for the system files inside $Extend.

Unlike records 0-11 these have no fixed record numbers; they are found
through $Extend's directory index. Each function returns a JSON-friendly
``details`` dict. Lists are capped at MAX_LISTED entries; totals are
always complete.
"""
import struct
from collections import Counter

from engine.metafiles.common import (
    ATTR_DATA,
    WELL_KNOWN_SIDS,
    filetime_to_datetime,
    format_guid,
    format_sid,
    mft_reference,
)
from engine.metafiles.i30 import read_directory_index
from engine.metafiles.stream import AttributeStream
from engine.metafiles.view_index import read_view_index

MAX_LISTED = 1000

# Common reparse tags (winnt.h). Unknown tags are shown in hex.
REPARSE_TAGS = {
    0xA0000003: "MOUNT_POINT (junction)",
    0xA000000C: "SYMLINK",
    0x80000017: "WOF (compressed system file)",
    0x8000001B: "APPEXECLINK",
    0x9000001A: "CLOUD (OneDrive placeholder)",
    0x9000101A: "CLOUD_1",
    0x9000201A: "CLOUD_2",
    0x80000013: "DEDUP",
    0x80000014: "NFS",
    0xA000001D: "LX_SYMLINK (WSL)",
    0x80000023: "AF_UNIX",
    0x80000025: "LX_FIFO",
    0x80000024: "LX_CHR",
    0x80000026: "LX_BLK",
    0x8000000A: "DFS",
    0x80000012: "DFSR",
    0xC0000004: "HSM",
}


def objid_details(parser, record):
    """$ObjId:$O maps object IDs (used by link tracking) to files."""
    entries = []
    total = 0
    for key, data in read_view_index(parser, record.record_number, "$O", record):
        total += 1
        if len(entries) >= MAX_LISTED or len(data) < 8:
            continue
        file_record, _ = mft_reference(struct.unpack_from("<Q", data)[0])
        entries.append({
            "object_id": format_guid(key),
            "record_number": file_record,
            "birth_volume_id": format_guid(data[8:24]),
            "birth_object_id": format_guid(data[24:40]),
        })
    return {"object_ids": total, "entries": entries}


def reparse_details(parser, record):
    """$Reparse:$R lists every reparse point (symlinks, junctions, ...)."""
    tags = Counter()
    entries = []
    for key, _ in read_view_index(parser, record.record_number, "$R", record):
        if len(key) < 12:
            continue
        tag, reference = struct.unpack_from("<IQ", key)
        label = REPARSE_TAGS.get(tag, f"0x{tag:08X}")
        tags[label] += 1
        if len(entries) < MAX_LISTED:
            entries.append({"tag": label, "record_number": mft_reference(reference)[0]})
    return {
        "reparse_points": sum(tags.values()),
        "by_tag": dict(tags.most_common()),
        "entries": entries,
    }


def quota_details(parser, record):
    """$Quota: disk usage per owner ($Q) and owner SIDs ($O)."""
    sids = {}
    for key, data in read_view_index(parser, record.record_number, "$O", record):
        if len(data) >= 4:
            sids[struct.unpack_from("<I", data)[0]] = format_sid(key)

    owners = []
    for key, data in read_view_index(parser, record.record_number, "$Q", record):
        if len(key) < 4 or len(data) < 48:
            continue
        owner_id = struct.unpack_from("<I", key)[0]
        _, flags, used, changed, warning, limit, exceeded = struct.unpack_from(
            "<IIQQqqQ", data
        )
        sid = format_sid(data, 48) or sids.get(owner_id)
        owners.append({
            "owner_id": owner_id,
            "sid": sid,
            "account": WELL_KNOWN_SIDS.get(sid),
            "bytes_used": used,
            "warning_limit": None if warning < 0 else warning,
            "hard_limit": None if limit < 0 else limit,
            "changed": filetime_to_datetime(changed),
            "limit_exceeded": filetime_to_datetime(exceeded),
        })
    return {"owners": len(owners), "entries": owners[:MAX_LISTED]}


def deleted_details(parser, record):
    """$Deleted holds files deleted while still open (POSIX delete, Win10+)."""
    index = read_directory_index(parser, record.record_number, scan_slack=False)
    names = [
        {"name": entry.key.name, "record_number": entry.file_record}
        for entry in index.live if entry.key.namespace != 2
    ]
    return {"pending_deletions": len(names), "entries": names[:MAX_LISTED]}


def repair_details(parser, record):
    """$Repair (self-healing NTFS): corruption log and configuration."""
    details = {}
    for name in ("", "$Config", "$Corrupt", "$Verify"):
        attribute = record.find(ATTR_DATA, name)
        if attribute is not None:
            details[f"{name or 'log'}_size"] = attribute.size
    config = record.find(ATTR_DATA, "$Config")
    if config is not None and config.resident and len(config.content) >= 8:
        details["config"] = config.content[:8].hex()
    return details


EXTEND_DETAIL_PARSERS = {
    "$ObjId": objid_details,
    "$Reparse": reparse_details,
    "$Quota": quota_details,
    "$Deleted": deleted_details,
    "$Repair": repair_details,
}
