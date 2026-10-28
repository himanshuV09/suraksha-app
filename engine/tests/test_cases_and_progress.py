"""Case lifecycle (status, listing, safe names), progress lines, version."""
import json
import sqlite3
from pathlib import Path

import main_cli
from engine import progress
from support.ntfs_image import FileSpec, NtfsImageBuilder


def run(capsys, *argv):
    exit_code = main_cli.main([str(arg) for arg in argv])
    captured = capsys.readouterr()
    return exit_code, json.loads(captured.out), captured.err


def image(tmp_path):
    builder = NtfsImageBuilder()
    builder.add_file(FileSpec(record_number=16, name="a.txt", data=b"a"))
    return builder.build(tmp_path / "disk.img")


def test_completed_analysis_is_listed_with_its_details(tmp_path, capsys):
    cases = tmp_path / "cases"
    exit_code, result, _ = run(
        capsys, "analyze", image(tmp_path).path, "--cases-dir", cases,
        "--case-name", "Theft 2026/041", "--investigator", "R. Rao",
        "--description", "USB drive seized at desk 4",
    )
    assert exit_code == 0, result

    _, listing, _ = run(capsys, "list-cases", "--cases-dir", cases)

    case = listing["cases"][0]
    assert case["case_name"] == "Theft 2026/041"
    assert case["investigator"] == "R. Rao"
    assert case["description"] == "USB drive seized at desk 4"
    assert case["status"] == "complete" and case["completed_at"]
    assert case["evidence_count"] > 0 and case["image_available"] is True
    assert case["engine_version"] == "1.0.0"
    # "/" in the case name cannot create sub-folders.
    assert Path(case["database_path"]).name == "Theft 2026_041.db"


def test_failed_analysis_is_marked_failed(tmp_path, capsys):
    not_ntfs = tmp_path / "blank.img"
    not_ntfs.write_bytes(bytes(1024 * 1024))

    exit_code, result, _ = run(capsys, "analyze", not_ntfs, "--cases-dir", tmp_path / "cases")

    assert exit_code == 1
    case_id = result["case_id"] or 1
    status = sqlite3.connect(result["database_path"]).execute(
        "SELECT status FROM cases WHERE case_id = ?", (case_id,)
    ).fetchone()[0]
    assert status == "failed"


def test_analysis_reports_progress_on_stderr(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(progress, "MIN_INTERVAL", 0.0)
    lines = []
    monkeypatch.setattr(progress.sys, "__stderr__", type("Sink", (), {
        "write": lambda self, text: lines.append(text), "flush": lambda self: None,
    })())

    run(capsys, "analyze", image(tmp_path).path, "--cases-dir", tmp_path / "cases")

    reports = [
        json.loads(line[len(progress.PREFIX):])
        for line in lines if line.startswith(progress.PREFIX)
    ]
    stages = [report["stage"] for report in reports]
    assert "Reading MFT records" in stages
    assert stages[-1] == "Analysis complete"
    mft = [r for r in reports if r["stage"] == "Reading MFT records"]
    assert mft[-1]["done"] == mft[-1]["total"]


def test_old_databases_get_the_new_case_columns(tmp_path):
    from database.case_database import Database
    from database.schema import DatabaseSchema

    database = Database()
    database.create_case("legacy", directory=tmp_path)
    database.cursor.execute(
        "CREATE TABLE cases (case_id INTEGER PRIMARY KEY AUTOINCREMENT, case_name TEXT NOT NULL, "
        "image_path TEXT, created_at TEXT, investigator TEXT, description TEXT)"
    )
    try:
        DatabaseSchema(database).create_schema()
        columns = [row[1] for row in database.cursor.execute("PRAGMA table_info(cases)")]
    finally:
        database.close()

    # Appended at the end: positional reads (image_path = column 2) still work.
    assert columns[:6] == ["case_id", "case_name", "image_path", "created_at", "investigator", "description"]
    assert {"status", "engine_version", "completed_at"} <= set(columns)


def test_version_command(capsys):
    exit_code, result, _ = run(capsys, "version")

    assert exit_code == 0
    assert result["engine_version"] == "1.0.0"
    assert result["frozen"] is False
