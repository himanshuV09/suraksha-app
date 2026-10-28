"""End-to-end tests on synthetic NTFS images, through the real CLI.

Each test builds a tiny disk image with tests/support/ntfs_image.py and
runs the same commands the Suraksha app runs.
"""
import base64
import json
import threading

import pytest

import main_cli
from support.jpeg_samples import TINY_JPEG
from support.ntfs_image import FileSpec, NtfsImageBuilder

PARTITION_OFFSET = 1024 * 1024
JPEG_LCN = 100


def run_cli(capsys, *argv):
    exit_code = main_cli.main([str(arg) for arg in argv])
    output = capsys.readouterr().out
    lines = output.strip().splitlines()
    assert len(lines) == 1, f"stdout must hold exactly one JSON line: {output!r}"
    return exit_code, json.loads(lines[0])


def analyze(capsys, image_path, cases_dir):
    exit_code, result = run_cli(
        capsys, "analyze", image_path, "--cases-dir", cases_dir
    )
    assert exit_code == 0, result
    assert result["success"] is True
    return result


def evidence_by_name(capsys, result):
    _, evidence = run_cli(
        capsys, "evidence", result["database_path"], result["case_id"]
    )
    return {item["filename"]: item for item in evidence["evidence"]}


def standard_image(**builder_options):
    builder = NtfsImageBuilder(**builder_options)
    builder.add_file(FileSpec(record_number=16, name="notes.txt", data=b"resident text"))
    builder.add_file(FileSpec(
        record_number=17,
        name="report.bin",
        data=b"NON-RESIDENT-CONTENT" * 300,
        runs=[(40, 2)],
    ))
    builder.add_file(FileSpec(record_number=18, name="deleted.txt", data=b"gone", deleted=True))
    builder.add_unallocated_payload("jpeg", JPEG_LCN, TINY_JPEG)
    return builder


@pytest.fixture(params=[0, PARTITION_OFFSET], ids=["bare-volume", "mbr-partition"])
def case(request, tmp_path, capsys):
    """An analyzed case, once as a bare volume and once inside an MBR partition."""
    image = standard_image(partition_offset=request.param).build(tmp_path / "disk.img")
    result = analyze(capsys, image.path, tmp_path / "cases")
    return image, result


# ---------------------------------------------------------------------
# Problem 1: the engine reports where it put the case database
# ---------------------------------------------------------------------

def test_analyze_returns_absolute_database_path(case, tmp_path):
    _, result = case

    assert result["database_path"] == str((tmp_path / "cases" / "USB Investigation.db").resolve())


def test_analyze_reports_missing_image_without_creating_a_case(tmp_path, capsys):
    exit_code, result = run_cli(
        capsys, "analyze", tmp_path / "missing.img", "--cases-dir", tmp_path / "cases"
    )

    assert exit_code == 1
    assert "Evidence image not found" in result["error"]
    assert not (tmp_path / "cases").exists()


# ---------------------------------------------------------------------
# Problem 2: partitioned images
# ---------------------------------------------------------------------

def test_files_are_listed_and_previewed_correctly(case, capsys):
    image, result = case
    files = evidence_by_name(capsys, result)

    assert {"notes.txt", "report.bin", "deleted.txt"} <= set(files)
    assert files["deleted.txt"]["deleted"]

    _, preview = run_cli(
        capsys, "preview", result["database_path"], files["report.bin"]["evidence_id"]
    )
    content = base64.b64decode(preview["content"])
    assert content.startswith(b"NON-RESIDENT-CONTENT")


def test_unallocated_regions_use_image_offsets(case, capsys):
    image, result = case

    _, regions = run_cli(
        capsys, "unallocated-regions", image.path, result["database_path"], result["case_id"]
    )

    region = next(r for r in regions["regions"] if r["start_cluster"] <= JPEG_LCN <= r["end_cluster"])
    assert region["start_offset"] == image.volume_offset + region["start_cluster"] * image.cluster_size

    index = region["index"]
    relative = image.payload_offsets["jpeg"] - region["start_offset"]
    _, raw = run_cli(
        capsys, "read-unallocated", image.path, result["database_path"],
        result["case_id"], index, relative, 4,
    )
    assert raw["data"] == TINY_JPEG[:4].hex()


def test_recovery_finds_jpeg_at_the_right_place(case, capsys):
    image, result = case

    exit_code, recovery = run_cli(
        capsys, "recover-unallocated", image.path, result["database_path"], result["case_id"]
    )

    assert exit_code == 0, recovery
    assert recovery["recovered_count"] == 1
    assert recovery["artifacts"][0]["source_offset"] == image.payload_offsets["jpeg"]

    _, stored = run_cli(
        capsys, "recovered-artifacts", result["database_path"], result["case_id"]
    )
    artifact = stored["artifacts"][0]
    assert artifact["start_cluster"] == JPEG_LCN
    assert artifact["size"] == len(TINY_JPEG)


# ---------------------------------------------------------------------
# Problem 3: fragmented $MFT
# ---------------------------------------------------------------------

def test_records_in_later_mft_runs_are_found(tmp_path, capsys):
    builder = NtfsImageBuilder(mft_runs=[(4, 2), (200, 2)])
    builder.add_file(FileSpec(record_number=9, name="in_second_run.txt", data=b"a"))
    builder.add_file(FileSpec(record_number=15, name="last_record.txt", data=b"b"))
    image = builder.build(tmp_path / "fragmented.img")

    files = evidence_by_name(capsys, analyze(capsys, image.path, tmp_path / "cases"))

    assert {"in_second_run.txt", "last_record.txt"} <= set(files)


def test_records_straddling_mft_runs_are_found(tmp_path, capsys):
    builder = NtfsImageBuilder(
        cluster_size=512, total_clusters=1024, mft_runs=[(10, 3), (500, 29)]
    )
    builder.add_file(FileSpec(record_number=1, name="straddles.txt", data=b"a"))
    builder.add_file(FileSpec(record_number=14, name="later.txt", data=b"b"))
    image = builder.build(tmp_path / "straddle.img")

    files = evidence_by_name(capsys, analyze(capsys, image.path, tmp_path / "cases"))

    assert {"straddles.txt", "later.txt"} <= set(files)


# ---------------------------------------------------------------------
# Problem 4: malformed records
# ---------------------------------------------------------------------

def test_malformed_record_is_skipped_and_reported(tmp_path, capsys):
    builder = NtfsImageBuilder()
    builder.add_file(FileSpec(record_number=16, name="before.txt", data=b"1"))
    builder.add_file(FileSpec(record_number=17, name="broken", malformed=True))
    builder.add_file(FileSpec(record_number=18, name="after.txt", data=b"2"))
    image = builder.build(tmp_path / "malformed.img")

    # The original parser looped forever on this image; fail instead of hanging.
    outcome = {}
    worker = threading.Thread(
        target=lambda: outcome.update(result=main_cli.main(
            ["analyze", image.path, "--cases-dir", str(tmp_path / "cases")]
        )),
        daemon=True,
    )
    worker.start()
    worker.join(timeout=30)
    assert not worker.is_alive(), "analysis hung on a malformed record"

    result = json.loads(capsys.readouterr().out)
    assert result["success"] is True
    assert result["corrupt_records"] == 1
    assert result["record_errors"][0]["record_number"] == 17
    assert "invalid length 0" in result["record_errors"][0]["error"]

    files = evidence_by_name(capsys, result)
    assert {"before.txt", "after.txt"} <= set(files)
    assert "broken" not in files


# ---------------------------------------------------------------------
# Problem 5: free-space commands do not re-parse the MFT
# ---------------------------------------------------------------------

def test_hex_reads_use_stored_regions(case, capsys, monkeypatch):
    image, result = case

    def fail(*args, **kwargs):
        raise AssertionError("read-unallocated must not re-parse the volume")

    monkeypatch.setattr("engine.api.unallocated_api.open_ntfs_volume", fail)

    exit_code, regions = run_cli(
        capsys, "unallocated-regions", image.path, result["database_path"], result["case_id"]
    )
    assert exit_code == 0 and regions["source"] == "database"

    exit_code, raw = run_cli(
        capsys, "read-unallocated", image.path, result["database_path"],
        result["case_id"], 0, 0, 16,
    )
    assert exit_code == 0 and raw["size"] == 16


def test_free_space_commands_reject_an_image_from_another_case(case, tmp_path, capsys):
    _, result = case
    other = standard_image().build(tmp_path / "other.img")

    exit_code, response = run_cli(
        capsys, "read-unallocated", other.path, result["database_path"],
        result["case_id"], 0, 0, 16,
    )

    assert exit_code == 1
    assert response["error_type"] == "EvidenceMismatchError"
