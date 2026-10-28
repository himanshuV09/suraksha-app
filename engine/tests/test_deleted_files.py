"""Deleted-file grading and restoration (recover-deleted)."""
import hashlib
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

import main_cli
from database.case_database import Database
from database.deleted_file_repository import DeletedFileRepository
from engine.api.deleted_file_api import relative_output_path
from support.jpeg_samples import TINY_JPEG
from support.ntfs_image import DEFAULT_FILETIME, FileSpec, NtfsImageBuilder

CLUSTER = 4096
ONE_HOUR = 36_000_000_000

INTACT_TEXT = b"meeting notes " * 500                 # 7000 bytes, 2 clusters
REUSED_DATA = b"R" * (2 * CLUSTER)
OLD_DATA, NEW_DATA = b"O" * 6000, b"N" * 6000
FAKE_JPEG = b"\x00" * (3 * CLUSTER - 100)              # .jpg that isn't one


def build(path):
    builder = NtfsImageBuilder(mft_runs=((4, 8), (200, 8)))
    add = builder.add_file
    add(FileSpec(record_number=40, name="intact.txt", data=INTACT_TEXT,
                 runs=[(60, 2)], deleted=True))
    add(FileSpec(record_number=41, name="photo.jpg", data=TINY_JPEG,
                 runs=[(70, 1)], deleted=True))
    add(FileSpec(record_number=42, name="reused.bin", data=REUSED_DATA,
                 runs=[(80, 2)], deleted=True))
    add(FileSpec(record_number=43, name="new.txt", data=b"L" * CLUSTER,
                 runs=[(80, 1)]))  # live file now owns half of reused.bin
    add(FileSpec(record_number=44, name="old.dat", data=OLD_DATA,
                 runs=[(90, 2)], deleted=True, filetime=DEFAULT_FILETIME))
    add(FileSpec(record_number=45, name="newer.dat", data=NEW_DATA,
                 runs=[(90, 2)], deleted=True, filetime=DEFAULT_FILETIME + ONE_HOUR))
    add(FileSpec(record_number=46, name="fake.jpg", data=FAKE_JPEG,
                 runs=[(100, 3)], deleted=True))
    add(FileSpec(record_number=47, name="tiny.txt", data=b"resident!", deleted=True))
    add(FileSpec(record_number=48, name="live.txt", data=b"still here"))
    return builder.build(path)


def run(capsys, *argv):
    exit_code = main_cli.main([str(arg) for arg in argv])
    return exit_code, json.loads(capsys.readouterr().out)


@pytest.fixture
def case(tmp_path, capsys):
    image = build(tmp_path / "deleted.img")
    exit_code, result = run(capsys, "analyze", image.path, "--cases-dir", tmp_path / "cases")
    assert exit_code == 0, result
    _, listing = run(capsys, "deleted-files", result["database_path"], result["case_id"])
    files = {item["filename"]: item for item in listing["files"]}
    return image, result, files


def test_summary_counts(case):
    _, result, _ = case

    assert result["deleted_recovery"] == {
        "deleted_files": 7,
        "deleted_recoverable": 4,   # intact.txt, photo.jpg, newer.dat, tiny.txt
        "deleted_partial": 2,       # reused.bin, fake.jpg
        "deleted_overwritten": 1,   # old.dat
        "deleted_no_data": 0,
        "deleted_recoverable_bytes": (
            len(INTACT_TEXT) + len(TINY_JPEG) + len(NEW_DATA) + len(b"resident!")
            + CLUSTER   # reused.bin: second cluster still original
            + CLUSTER   # fake.jpg: middle cluster (first and last fail the check)
        ),
    }


def test_intact_file_is_recoverable(case):
    item = case[2]["intact.txt"]

    assert item["status"] == "recoverable"
    assert item["recoverable_percent"] == 100.0
    assert item["unreliable_ranges"] == []
    assert item["content_check"] == "unknown"  # no rule for .txt


def test_jpeg_content_is_verified(case):
    assert case[2]["photo.jpg"]["content_check"] == "verified"
    assert case[2]["photo.jpg"]["status"] == "recoverable"


def test_clusters_reused_by_a_live_file(case):
    item = case[2]["reused.bin"]

    assert item["status"] == "partial"
    assert item["reused_clusters"] == 1 and item["free_clusters"] == 1
    assert item["unreliable_ranges"] == [[0, CLUSTER]]
    assert item["overwritten_by"] == ["./new.txt"]


def test_later_deleted_file_owns_shared_clusters(case):
    old, newer = case[2]["old.dat"], case[2]["newer.dat"]

    assert old["status"] == "overwritten"
    assert old["overwritten_by"] == ["./newer.dat (deleted)"]
    assert newer["status"] == "recoverable"  # bitmap alone would rate both intact


def test_content_mismatch_marks_first_and_last_cluster(case):
    item = case[2]["fake.jpg"]

    assert item["content_check"] == "mismatch"
    assert item["status"] == "partial"
    assert item["unreliable_ranges"] == [[0, CLUSTER], [2 * CLUSTER, len(FAKE_JPEG)]]


def test_resident_deleted_file_is_recoverable(case):
    assert case[2]["tiny.txt"]["status"] == "recoverable"
    assert case[2]["tiny.txt"]["resident"] is True


def test_live_files_are_not_listed(case):
    assert "live.txt" not in case[2] and "new.txt" not in case[2]


def test_recover_deleted_restores_names_bytes_hashes_and_times(case, capsys, tmp_path):
    image, result, _ = case
    destination = tmp_path / "restored"

    exit_code, response = run(
        capsys, "recover-deleted", image.path, result["database_path"],
        result["case_id"], destination,
    )

    assert exit_code == 0, response
    restored = {Path(item["path"]).name: item for item in response["files"] if "path" in item}
    # Default: recoverable + partial only.
    assert set(restored) == {"intact.txt", "photo.jpg", "newer.dat", "tiny.txt", "reused.bin", "fake.jpg"}

    assert (destination / "intact.txt").read_bytes() == INTACT_TEXT
    assert (destination / "photo.jpg").read_bytes() == TINY_JPEG
    assert (destination / "newer.dat").read_bytes() == NEW_DATA
    assert (destination / "tiny.txt").read_bytes() == b"resident!"
    assert restored["photo.jpg"]["sha256"] == hashlib.sha256(TINY_JPEG).hexdigest()

    # Partial files say which bytes are not original.
    assert restored["reused.bin"]["unreliable_ranges"] == [[0, CLUSTER]]

    # Original modified time (2024-01-01 UTC) is restored.
    expected = (datetime(2024, 1, 1) - datetime(1970, 1, 1)).total_seconds()
    assert os.path.getmtime(destination / "intact.txt") == pytest.approx(expected, abs=1)

    manifest = json.loads(Path(response["manifest"]).read_text(encoding="utf-8"))
    assert len(manifest["files"]) == 6


def test_recover_selected_records_without_overwriting(case, capsys, tmp_path):
    image, result, _ = case
    destination = tmp_path / "restored"
    destination.mkdir()
    (destination / "intact.txt").write_bytes(b"do not touch")

    exit_code, response = run(
        capsys, "recover-deleted", image.path, result["database_path"],
        result["case_id"], destination, "--records", "40",
    )

    assert exit_code == 0
    assert (destination / "intact.txt").read_bytes() == b"do not touch"
    assert (destination / "intact (record 40).txt").read_bytes() == INTACT_TEXT
    assert response["recovered_count"] == 1


def test_overwritten_files_only_when_asked(case, capsys, tmp_path):
    image, result, _ = case

    _, response = run(
        capsys, "recover-deleted", image.path, result["database_path"],
        result["case_id"], tmp_path / "all", "--status", "overwritten",
    )

    assert [Path(item["path"]).name for item in response["files"]] == ["old.dat"]


def test_unknown_status_is_a_usage_error(case, capsys, tmp_path):
    image, result, _ = case

    exit_code, response = run(
        capsys, "recover-deleted", image.path, result["database_path"],
        result["case_id"], tmp_path / "x", "--status", "maybe",
    )

    assert exit_code == 2 and response["error_type"] == "UsageError"


@pytest.mark.parametrize("full_path, expected", [
    ("./docs/report.docx", Path("docs", "report.docx")),
    ("../../windows/system32/evil.dll", Path("_", "_", "windows", "system32", "evil.dll")),
    ("./CON.txt", Path("_CON.txt")),
    ("./a:b?.txt", Path("a_b_.txt")),
    ("", Path("record_9")),
])
def test_output_paths_are_safe(full_path, expected):
    assert relative_output_path(full_path, "", 9) == expected


def test_older_database_gets_new_columns(tmp_path):
    database = Database()
    database.create_case("old", directory=tmp_path)
    database.cursor.execute(
        "CREATE TABLE deleted_files (deleted_file_id INTEGER PRIMARY KEY, case_id INTEGER, "
        "record_number INTEGER, sequence_number INTEGER, filename TEXT, full_path TEXT, "
        "file_size INTEGER, resident INTEGER, status TEXT, total_clusters INTEGER, "
        "free_clusters INTEGER, reused_clusters INTEGER, recoverable_bytes INTEGER, "
        "recoverable_percent REAL, overwritten_by TEXT, created TEXT, modified TEXT, "
        "accessed TEXT, mft_modified TEXT)"
    )
    try:
        DeletedFileRepository(database).ensure_schema()
        columns = {row[1] for row in database.cursor.execute("PRAGMA table_info(deleted_files)")}
    finally:
        database.close()

    assert {"unreliable_ranges", "content_check"} <= columns
