"""NTFS metafile parsing: $Volume, $MFTMirr, $LogFile, $UsnJrnl, $I30, export.

Builds one synthetic volume containing each structure and checks the
results through the real CLI, plus unit tests for the parsers.
"""
import json
import os
import struct

import pytest

import main_cli
from engine.metafiles.common import ATTR_FILE_NAME
from engine.metafiles.i30 import _carve, _dedupe_ghosts
from engine.metafiles.usn_journal import iter_usn_records, parse_usn_record
from support import ntfs_structures as nt
from support.ntfs_image import FileSpec, NtfsImageBuilder, RawAttribute

ATTR_VOLUME_NAME = 0x60
ATTR_VOLUME_INFORMATION = 0x70
ATTR_DATA = 0x80
ATTR_INDEX_ROOT = 0x90
ATTR_OBJECT_ID = 0x40

CLUSTER = 4096
# Record numbers as on a real volume: $Extend children from 24, user files later.
QUOTA, OBJID, REPARSE, RMMETADATA, REPAIR = 24, 25, 26, 27, 28
USN_RECORD = 40
NOTES, DELETED, LONG_NAME = 41, 42, 43
HIDDEN_RESERVED = 13

JOURNAL_LCN = 30
SPARSE_CLUSTERS = 4

USER_SID = nt.sid(21, 111, 222, 333, 1001)
SYSTEM_SID = nt.sid(18)

# System records the synthetic image leaves out (reported, never fatal).
MISSING_FROM_TEST_IMAGE = {"$AttrDef"}

USN_DATA = (
    nt.usn_record(0, DELETED, 5, "deleted_secret.docx", reason=0x00000100)
    + nt.usn_record(96, DELETED, 5, "deleted_secret.docx", reason=0x80000200,
                    filetime=nt.DEFAULT_FILETIME + 2 * nt.ONE_HOUR)
)


def _secure_stream():
    first = nt.sds_entry(0x100, USER_SID, 0)
    second_offset = (len(first) + 15) & ~15
    second = nt.sds_entry(0x101, SYSTEM_SID, second_offset)
    return first.ljust(second_offset, b"\0") + second


def _extend_entry(record, name, directory=False, parent=11):
    return (record, nt.file_name(name, parent, parent_sequence=parent, directory=directory))


def build_metafile_image(path, logfile_bytes=None):
    # Two MFT pieces (records 0-31 and 32-63), as on a volume that grew.
    builder = NtfsImageBuilder(mft_runs=((4, 8), (200, 8)))

    builder.add_file(FileSpec(  # $MFTMirr: copies of records 0-3
        record_number=1, name="$MFTMirr", data=bytes(CLUSTER),
        runs=[(13, 1)], sequence=1,
    ))
    logfile_bytes = logfile_bytes or nt.logfile(
        [nt.file_name("old_report.docx", 5)], lsn=0x5000, clean=False,
    )
    builder.add_file(FileSpec(
        record_number=2, name="$LogFile", data=logfile_bytes,
        runs=[(20, len(logfile_bytes) // CLUSTER)], sequence=2,
    ))
    builder.add_file(FileSpec(
        record_number=3, name="$Volume", sequence=3,
        extra_attributes=[
            RawAttribute(ATTR_VOLUME_NAME, "EVIDENCE".encode("utf-16le")),
            RawAttribute(ATTR_VOLUME_INFORMATION, nt.volume_information(flags=0x0001)),
            RawAttribute(ATTR_OBJECT_ID, nt.guid("11111111-2222-3333-4444-555555555555")),
        ],
    ))
    builder.add_file(FileSpec(  # root directory with a ghost in its index slack
        record_number=5, name=".", directory=True, sequence=5,
        extra_attributes=[RawAttribute(ATTR_INDEX_ROOT, nt.index_root(
            entries=[(NOTES, nt.file_name("notes.txt", 5)),
                     (LONG_NAME, nt.file_name("long name.txt", 5))],
            slack=nt.index_entry(DELETED, nt.file_name("deleted_secret.docx", 5)),
        ), name="$I30")],
    ))
    builder.add_file(FileSpec(  # $Boot covers the boot sector cluster
        record_number=7, name="$Boot", runs=[(0, 1)], sequence=7,
    ))
    builder.add_file(FileSpec(  # $BadClus:$Bad spans the volume, all sparse
        record_number=8, name="$BadClus", sequence=8,
        extra_attributes=[RawAttribute(
            ATTR_DATA, name="$Bad", runs=[(None, 256)], real_size=256 * CLUSTER,
        )],
    ))
    sds = _secure_stream()
    builder.add_cluster_data(190, sds)
    builder.add_file(FileSpec(
        record_number=9, name="$Secure", sequence=9,
        extra_attributes=[
            RawAttribute(ATTR_DATA, name="$SDS", runs=[(190, 1)], real_size=len(sds)),
            RawAttribute(ATTR_INDEX_ROOT, nt.view_index_root(
                [(struct.pack("<I", 0x100), bytes(20)), (struct.pack("<I", 0x101), bytes(20))]
            ), name="$SII"),
        ],
    ))
    builder.add_file(FileSpec(
        record_number=10, name="$UpCase", sequence=10,
        data=nt.upcase_table(), runs=[(150, 32)],
        extra_attributes=[RawAttribute(ATTR_DATA, nt.upcase_info(), name="$Info")],
    ))
    builder.add_file(FileSpec(
        record_number=11, name="$Extend", directory=True, sequence=11,
        extra_attributes=[RawAttribute(ATTR_INDEX_ROOT, nt.index_root(entries=[
            _extend_entry(QUOTA, "$Quota"),
            _extend_entry(OBJID, "$ObjId"),
            _extend_entry(REPARSE, "$Reparse"),
            _extend_entry(RMMETADATA, "$RmMetadata", directory=True),
            _extend_entry(USN_RECORD, "$UsnJrnl"),
        ]), name="$I30")],
    ))
    builder.add_file(FileSpec(  # data hidden in a reserved MFT record
        record_number=HIDDEN_RESERVED, name="hidden", data=b"smuggled bytes",
    ))
    builder.add_file(FileSpec(
        record_number=QUOTA, name="$Quota", parent=11, parent_sequence=11,
        extra_attributes=[
            RawAttribute(ATTR_INDEX_ROOT, nt.view_index_root(
                [(USER_SID, struct.pack("<I", 0x101))]), name="$O"),
            RawAttribute(ATTR_INDEX_ROOT, nt.view_index_root(
                [(struct.pack("<I", 0x101), nt.quota_entry(5000, USER_SID))]), name="$Q"),
        ],
    ))
    builder.add_file(FileSpec(
        record_number=OBJID, name="$ObjId", parent=11, parent_sequence=11,
        extra_attributes=[RawAttribute(ATTR_INDEX_ROOT, nt.view_index_root([(
            nt.guid("AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"),
            struct.pack("<Q", NOTES | (1 << 48))
            + nt.guid("12345678-1234-1234-1234-123456789ABC") + bytes(32),
        )]), name="$O")],
    ))
    builder.add_file(FileSpec(
        record_number=REPARSE, name="$Reparse", parent=11, parent_sequence=11,
        extra_attributes=[RawAttribute(ATTR_INDEX_ROOT, nt.view_index_root(
            [(struct.pack("<IQ", 0xA000000C, LONG_NAME | (1 << 48)), b"")]
        ), name="$R")],
    ))
    builder.add_file(FileSpec(
        record_number=RMMETADATA, name="$RmMetadata", directory=True,
        parent=11, parent_sequence=11,
        extra_attributes=[RawAttribute(ATTR_INDEX_ROOT, nt.index_root(
            entries=[_extend_entry(REPAIR, "$Repair", parent=RMMETADATA)],
        ), name="$I30")],
    ))
    builder.add_file(FileSpec(
        record_number=REPAIR, name="$Repair", parent=RMMETADATA, parent_sequence=RMMETADATA,
        extra_attributes=[RawAttribute(ATTR_DATA, bytes.fromhex("0100000003000000"), name="$Config")],
    ))
    builder.add_file(FileSpec(
        record_number=USN_RECORD, name="$UsnJrnl", parent=11, parent_sequence=11,
        extra_attributes=[
            RawAttribute(ATTR_DATA, nt.usn_max(), name="$Max"),
            RawAttribute(
                ATTR_DATA, name="$J",
                runs=[(None, SPARSE_CLUSTERS), (JOURNAL_LCN, 1)],
                real_size=SPARSE_CLUSTERS * CLUSTER + len(USN_DATA),
            ),
        ],
    ))
    builder.add_cluster_data(JOURNAL_LCN, USN_DATA)
    builder.add_file(FileSpec(record_number=NOTES, name="notes.txt", data=b"live file"))
    builder.add_file(FileSpec(  # long Win32 name followed by its 8.3 alias
        record_number=LONG_NAME, name="long name.txt", data=b"x",
        extra_attributes=[RawAttribute(
            ATTR_FILE_NAME, nt.file_name("LONGNA~1.TXT", 5, namespace=2)
        )],
    ))
    return builder.build(path)


def run(capsys, *argv):
    exit_code = main_cli.main([str(arg) for arg in argv])
    return exit_code, json.loads(capsys.readouterr().out)


@pytest.fixture
def analyzed(tmp_path, capsys):
    image = build_metafile_image(tmp_path / "metafiles.img")
    exit_code, result = run(capsys, "analyze", image.path, "--cases-dir", tmp_path / "cases")
    assert exit_code == 0, result
    return image, result


def metafile(capsys, result, name):
    _, listing = run(capsys, "metafiles", result["database_path"], result["case_id"])
    return next(item for item in listing["metafiles"] if item["name"] == name)


def timeline(capsys, result):
    _, response = run(capsys, "timeline", result["database_path"], result["case_id"])
    return response["events"]


# ---------------------------------------------------------------------
# Analysis summary
# ---------------------------------------------------------------------

def test_analysis_reports_volume_label_and_metafile_counts(analyzed):
    _, result = analyzed

    assert result["volume_label"] == "EVIDENCE"
    counts = result["metafile_counts"]
    assert counts["usn_records"] == 2
    assert counts["logfile_entries"] == 1
    assert counts["i30_ghost_entries"] == 1

    # The test image omits these records; each is reported, not fatal.
    warned = {warning.split(":")[0] for warning in result["warnings"]}
    hidden = "Reserved MFT record 13 holds 14 bytes of data"
    assert warned == MISSING_FROM_TEST_IMAGE | {hidden}
    assert result["metafile_counts"]["suspicious_reserved_records"] == 1


def test_every_system_metafile_is_listed(analyzed, capsys):
    _, result = analyzed
    _, listing = run(capsys, "metafiles", result["database_path"], result["case_id"])

    names = {item["name"] for item in listing["metafiles"]}
    assert {"$MFT", "$MFTMirr", "$LogFile", "$Volume", "$AttrDef", "$Bitmap",
            "$Boot", "$BadClus", "$Secure", "$UpCase", "$Extend",
            "$Extend\\$UsnJrnl"} <= names


# ---------------------------------------------------------------------
# Individual metafiles
# ---------------------------------------------------------------------

def test_volume_details(analyzed, capsys):
    details = metafile(capsys, analyzed[1], "$Volume")["details"]

    assert details == {
        "label": "EVIDENCE", "ntfs_version": "3.1", "flags": ["DIRTY"], "dirty": True,
        "volume_object_id": "11111111-2222-3333-4444-555555555555",
    }


def test_mft_mirror_matches_mft(analyzed, capsys):
    details = metafile(capsys, analyzed[1], "$MFTMirr")["details"]

    assert details["mirrored_records"] == 4
    assert details["matches_mft"] is True


def test_bitmap_and_boot_details(analyzed, capsys):
    bitmap = metafile(capsys, analyzed[1], "$Bitmap")["details"]
    boot = metafile(capsys, analyzed[1], "$Boot")["details"]

    assert bitmap["total_clusters"] == 256
    assert bitmap["allocated_clusters"] + bitmap["free_clusters"] == 256
    assert boot["backup_available"] is False  # test image ends with the volume


def test_extend_lists_its_children(analyzed, capsys):
    details = metafile(capsys, analyzed[1], "$Extend")["details"]

    assert {"name": "$UsnJrnl", "record_number": USN_RECORD} in details["children"]
    assert len(details["children"]) == 5


def test_whole_extend_tree_is_inventoried(analyzed, capsys):
    _, listing = run(capsys, "metafiles", analyzed[1]["database_path"], analyzed[1]["case_id"])
    names = {item["name"] for item in listing["metafiles"]}

    assert {"$Extend\$Quota", "$Extend\$ObjId", "$Extend\$Reparse",
            "$Extend\$RmMetadata", "$Extend\$RmMetadata\$Repair",
            "$Extend\$UsnJrnl"} <= names


def test_object_ids_map_to_files(analyzed, capsys):
    details = metafile(capsys, analyzed[1], "$Extend\$ObjId")["details"]

    assert details["object_ids"] == 1
    entry = details["entries"][0]
    assert entry["object_id"] == "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"
    assert entry["record_number"] == NOTES
    assert entry["path"] == "./notes.txt"
    assert entry["birth_volume_id"] == "12345678-1234-1234-1234-123456789ABC"


def test_reparse_points_are_listed_by_tag(analyzed, capsys):
    details = metafile(capsys, analyzed[1], "$Extend\$Reparse")["details"]

    assert details["by_tag"] == {"SYMLINK": 1}
    assert details["entries"][0]["path"] == "./long name.txt"


def test_quota_usage_per_owner(analyzed, capsys):
    details = metafile(capsys, analyzed[1], "$Extend\$Quota")["details"]

    owner = details["entries"][0]
    assert owner["sid"] == "S-1-5-21-111-222-333-1001"
    assert owner["bytes_used"] == 5000
    assert owner["hard_limit"] is None


def test_repair_config_is_read(analyzed, capsys):
    details = metafile(capsys, analyzed[1], "$Extend\$RmMetadata\$Repair")["details"]

    assert details["config"] == "0100000003000000"


def test_secure_descriptors_indexes_and_owners(analyzed, capsys):
    details = metafile(capsys, analyzed[1], "$Secure")["details"]

    assert details["security_descriptors"] == 2
    assert details["sii_entries"] == 2
    owners = {owner["sid"]: owner["account"] for owner in details["owners"]}
    assert owners == {"S-1-5-21-111-222-333-1001": None, "S-1-5-18": "SYSTEM"}


def test_upcase_table_and_info(analyzed, capsys):
    details = metafile(capsys, analyzed[1], "$UpCase")["details"]

    assert details["valid"] is True
    assert details["formatted_by_windows"] == "10.0 build 19041"


def test_logfile_restart_area_reports_unclean_shutdown(analyzed, capsys):
    details = metafile(capsys, analyzed[1], "$LogFile")["details"]

    assert details["current_lsn"] == 0x5000  # newer of the two restart pages
    assert details["clean_dismount"] is False


def test_mft_bitmap_matches_enumeration(analyzed, capsys):
    details = metafile(capsys, analyzed[1], "$MFT")["details"]

    assert details["fragmented"] is True
    assert details["bitmap_records_in_use"] == details["enumerated_records_in_use"]
    assert details["bitmap_matches_records"] is True


def test_root_directory_is_inventoried(analyzed, capsys):
    details = metafile(capsys, analyzed[1], ".")["details"]

    assert details["live_entries"] == 2
    assert details["deleted_entries_in_index"] == 1


def test_reserved_record_with_data_is_flagged(analyzed, capsys):
    item = metafile(capsys, analyzed[1], "[Reserved 13]")

    assert item["details"]["suspicious"] is True
    assert item["details"]["data_bytes"] == len(b"smuggled bytes")


def test_usn_journal_is_parsed_through_the_sparse_region(analyzed, capsys):
    item = metafile(capsys, analyzed[1], "$Extend\\$UsnJrnl")
    details = item["details"]

    assert {s["name"] for s in item["streams"]} >= {"$J", "$Max"}
    assert details["record_count"] == 2
    assert details["j_size"] == SPARSE_CLUSTERS * CLUSTER + len(USN_DATA)
    assert details["max_size"] == 32 * 1024 * 1024
    assert details["reason_counts"]["FILE_DELETE"] == 1


def test_logfile_details(analyzed, capsys):
    details = metafile(capsys, analyzed[1], "$LogFile")["details"]

    assert details["restart_pages"] == 2
    assert details["record_pages"] == 1
    assert details["recovered_file_names"] == 1
    assert details["log_version"] == "1.1"


# ---------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------

def test_usn_deletion_appears_on_the_timeline_with_its_path(analyzed, capsys):
    events = timeline(capsys, analyzed[1])

    deletion = next(e for e in events if e["source"] == "USN" and e["event_type"] == "Deleted")
    assert deletion["full_path"] == "./deleted_secret.docx"
    assert deletion["record_number"] == DELETED
    assert "FILE_DELETE" in deletion["description"]


def test_logfile_and_i30_events_appear_on_the_timeline(analyzed, capsys):
    events = timeline(capsys, analyzed[1])

    logfile_names = {e["filename"] for e in events if e["source"] == "LOGFILE"}
    ghosts = [e for e in events if e["source"] == "I30"]

    assert "old_report.docx" in logfile_names
    assert {e["filename"] for e in ghosts} == {"deleted_secret.docx"}
    assert all(e["deleted"] for e in ghosts)
    assert "slack" in ghosts[0]["description"]


def test_long_name_is_preferred_over_its_8_3_alias(analyzed, capsys):
    _, result = analyzed
    _, evidence = run(capsys, "evidence", result["database_path"], result["case_id"])

    names = {item["record_number"]: item["filename"] for item in evidence["evidence"]}
    assert names[LONG_NAME] == "long name.txt"


# ---------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------

def test_extract_metafiles_writes_raw_streams(analyzed, capsys, tmp_path):
    image, result = analyzed
    destination = tmp_path / "export"

    exit_code, response = run(
        capsys, "extract-metafiles", image.path, result["database_path"],
        result["case_id"], destination,
    )

    assert exit_code == 0, response
    failed = {item["name"] for item in response["files"] if "error" in item}
    assert failed == MISSING_FROM_TEST_IMAGE
    files = {
        os.path.basename(item["path"]): item
        for item in response["files"] if "path" in item
    }

    journal = (destination / "_UsnJrnl__J").read_bytes()
    assert len(journal) == SPARSE_CLUSTERS * CLUSTER + len(USN_DATA)
    assert journal[:SPARSE_CLUSTERS * CLUSTER] == bytes(SPARSE_CLUSTERS * CLUSTER)
    assert journal[SPARSE_CLUSTERS * CLUSTER:] == USN_DATA

    assert files["_MFT"]["size"] == 64 * 1024
    assert (destination / "_LogFile").read_bytes()[:4] == b"RSTR"

    # A stream with no data on disk is reported, not written as zeros.
    bad = next(item for item in response["files"] if item["name"] == "$BadClus:$Bad")
    assert "entirely sparse" in bad["skipped"]
    assert not (destination / "_BadClus__Bad").exists()
    assert response["skipped_count"] == 1


# ---------------------------------------------------------------------
# Robustness
# ---------------------------------------------------------------------

def test_damaged_logfile_page_is_counted_not_fatal(tmp_path, capsys):
    logfile_bytes = bytearray(nt.logfile([nt.file_name("x.txt", 5)]))
    logfile_bytes[2 * 4096 + 510] ^= 0xFF  # break the RCRD page's fixup
    image = build_metafile_image(tmp_path / "bad.img", bytes(logfile_bytes))

    exit_code, result = run(capsys, "analyze", image.path, "--cases-dir", tmp_path / "cases")

    assert exit_code == 0
    details = metafile(capsys, result, "$LogFile")["details"]
    assert details["unreadable_pages"] == 1
    assert details["record_pages"] == 0


def test_image_without_metafile_extras_still_analyzes(tmp_path, capsys):
    builder = NtfsImageBuilder()
    builder.add_file(FileSpec(record_number=16, name="a.txt", data=b"a"))
    image = builder.build(tmp_path / "plain.img")

    exit_code, result = run(capsys, "analyze", image.path, "--cases-dir", tmp_path / "cases")

    assert exit_code == 0
    assert result["metafile_counts"]["usn_records"] == 0
    assert result["volume_label"] == ""


# ---------------------------------------------------------------------
# Parser units
# ---------------------------------------------------------------------

def test_usn_record_split_across_segments_is_joined():
    data = USN_DATA
    cut = 40  # inside the first record
    segments = [(0, data[:cut], False), (cut, data[cut:], True)]

    records = list(iter_usn_records(segments))

    assert [r.name for r in records] == ["deleted_secret.docx"] * 2
    assert records[1].action == "Deleted"


def test_sparse_gap_discards_partial_record():
    data = USN_DATA
    segments = [(0, data[:40], False), (8192, data[96:], False)]

    records = list(iter_usn_records(segments))

    assert len(records) == 1 and records[0].usn == 96


def test_parse_usn_record_rejects_garbage():
    assert parse_usn_record(bytes(64), 0) == (None, 0)
    assert parse_usn_record(b"\xff" * 64, 0) == (None, 0)


def test_ghost_requires_this_directory_as_parent():
    other_parent = nt.index_entry(9, nt.file_name("elsewhere.txt", 77))
    ours = nt.index_entry(9, nt.file_name("ours.txt", 5))
    slack = bytes(16) + other_parent + ours

    ghosts = _carve(slack, 0, len(slack), directory_record=5, location="slack")

    assert [g.key.name for g in ghosts] == ["ours.txt"]


def test_ghost_still_listed_live_is_dropped():
    entry = _carve(nt.index_entry(9, nt.file_name("kept.txt", 5)), 0, 200, 5, "slack")
    live = list(entry)

    assert _dedupe_ghosts(live, entry) == []
