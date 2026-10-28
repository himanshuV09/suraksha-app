"""Slack space (MFT records, files) and reassembly of fragmented files."""
import io
import json
import random
import zipfile
from pathlib import Path

import main_cli
from support import ntfs_structures as nt
from support.jpeg_samples import TINY_JPEG
from support.ntfs_image import FileSpec, NtfsImageBuilder

CLUSTER = 4096


def run(capsys, *argv):
    exit_code = main_cli.main([str(arg) for arg in argv])
    return exit_code, json.loads(capsys.readouterr().out)


def analyze(capsys, image, tmp_path):
    exit_code, result = run(capsys, "analyze", image.path, "--cases-dir", tmp_path / "cases")
    assert exit_code == 0, result
    return result


def stored_zip(size):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as archive:
        archive.writestr("data.bin", random.Random(1).randbytes(size))
    return buffer.getvalue()


def split_image(tmp_path, payload, first_clusters=2):
    """Payload in free space, interrupted by a live file's two clusters."""
    builder = NtfsImageBuilder()
    head, tail = payload[:first_clusters * CLUSTER], payload[first_clusters * CLUSTER:]
    builder.add_unallocated_payload("head", 40, head)
    gap = 40 + first_clusters
    builder.add_file(FileSpec(record_number=16, name="in_the_way.bin",
                              data=b"L" * 2 * CLUSTER, runs=[(gap, 2)]))
    builder.add_unallocated_payload("tail", gap + 2, tail)
    return builder.build(tmp_path / "split.img")


# ----------------------------------------------------------------------
# Fragmented files
# ----------------------------------------------------------------------

def test_fragmented_zip_is_reassembled_exactly(tmp_path, capsys):
    payload = stored_zip(3 * CLUSTER)
    image = split_image(tmp_path, payload)
    result = analyze(capsys, image, tmp_path)

    _, recovery = run(capsys, "recover-unallocated", image.path, result["database_path"], result["case_id"])
    assert recovery["recovered_fragmented"] == 1, recovery

    _, listing = run(capsys, "recovered-artifacts", result["database_path"], result["case_id"])
    artifact = listing["artifacts"][0]
    assert artifact["source_type"] == "UNALLOCATED_FRAGMENTED"
    assert artifact["confidence"] == 0.4
    assert artifact["fragments"] == [[40 * CLUSTER, 2 * CLUSTER], [44 * CLUSTER, len(payload) - 2 * CLUSTER]]

    _, export = run(capsys, "export-recovered", image.path, result["database_path"],
                    result["case_id"], tmp_path / "out")
    assert export["hash_mismatches"] == 0
    assert Path(export["files"][0]["path"]).read_bytes() == payload


def test_fragmented_jpeg_is_not_reassembled(tmp_path, capsys):
    # JPEG has no checksum, so a wrong join could not be detected.
    image = split_image(tmp_path, TINY_JPEG[:300] + bytes(2 * CLUSTER) + TINY_JPEG[300:], first_clusters=1)
    result = analyze(capsys, image, tmp_path)

    _, recovery = run(capsys, "recover-unallocated", image.path, result["database_path"], result["case_id"])

    assert recovery["recovered_fragmented"] == 0
    assert all(item["signature"] != "JPEG" or "fragments" not in item for item in recovery["artifacts"])


# ----------------------------------------------------------------------
# MFT record slack
# ----------------------------------------------------------------------

def test_old_name_in_mft_record_slack_reaches_the_timeline(tmp_path, capsys):
    builder = NtfsImageBuilder()
    old_name = nt.file_name("previous_tenant.xlsx", 5, filetime=nt.DEFAULT_FILETIME - 400 * nt.ONE_HOUR)
    builder.add_file(FileSpec(record_number=16, name="new.txt", data=b"n",
                              record_slack=bytes(16) + old_name))
    image = builder.build(tmp_path / "slack.img")
    result = analyze(capsys, image, tmp_path)

    assert result["metafile_counts"]["mft_slack_entries"] == 1
    _, timeline = run(capsys, "timeline", result["database_path"], result["case_id"])
    events = [e for e in timeline["events"] if e["source"] == "MFT_SLACK"]
    assert {e["filename"] for e in events} == {"previous_tenant.xlsx"}
    assert "record now holds: ./new.txt" in events[0]["description"]


# ----------------------------------------------------------------------
# File slack
# ----------------------------------------------------------------------

def test_file_slack_returns_leftover_bytes_and_strings(tmp_path, capsys):
    builder = NtfsImageBuilder()
    leftover = b"\x00" * 100 + b"old password: hunter2 " + b"\x00" * 50
    # Earlier content of the clusters, then the new 5,000-byte file over it.
    builder.add_cluster_data(60, bytes(5000) + leftover)
    builder.add_file(FileSpec(record_number=16, name="report.txt", data=b"r" * 5000, runs=[(60, 2)]))
    image = builder.build(tmp_path / "fslack.img")
    result = analyze(capsys, image, tmp_path)
    _, evidence = run(capsys, "evidence", result["database_path"], result["case_id"])
    evidence_id = next(e["evidence_id"] for e in evidence["evidence"] if e["filename"] == "report.txt")

    exit_code, slack = run(capsys, "file-slack", result["database_path"], evidence_id)

    assert exit_code == 0, slack
    assert slack["slack_size"] == 2 * CLUSTER - 5000
    assert slack["slack_offset"] == 5000
    assert bytes.fromhex(slack["data"]).startswith(leftover)
    assert "old password: hunter2 " in slack["strings"]
