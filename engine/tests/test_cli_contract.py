"""The CLI output contract the desktop app depends on (problem 6).

* stdout holds exactly one JSON object.
* Success -> exit 0, "success": true.
* Failure -> exit 1 (2 for bad usage), "success": false, and a readable
  "error" message plus "error_type".
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

import main_cli

ENGINE_DIR = Path(main_cli.__file__).resolve().parent


def run(capsys, *argv):
    exit_code = main_cli.main([str(arg) for arg in argv])
    captured = capsys.readouterr()
    lines = captured.out.strip().splitlines()
    assert len(lines) == 1, captured.out
    return exit_code, json.loads(lines[0]), captured.err


@pytest.mark.parametrize("argv", [
    [],
    ["no-such-command"],
    ["evidence", "case.db"],
    ["evidence", "case.db", "zero"],
    ["evidence", "case.db", "0"],
    ["timeline", "case.db", "1", "hourly"],
    ["read-unallocated", "a.img", "case.db", "1", "0", "0", "0"],
])
def test_bad_usage_exits_2_with_a_usage_message(capsys, argv):
    exit_code, result, _ = run(capsys, *argv)

    assert exit_code == main_cli.EXIT_USAGE
    assert result["success"] is False
    assert result["error_type"] == "UsageError"
    assert result["error"].startswith("Usage")


def test_runtime_failure_exits_1_with_the_real_message(capsys, tmp_path):
    exit_code, result, stderr = run(capsys, "evidence", tmp_path / "missing.db", 1)

    assert exit_code == main_cli.EXIT_FAILURE
    assert result["success"] is False
    assert "Case database not found" in result["error"]
    assert result["error_type"] == "FileNotFoundError"
    assert "Traceback" in stderr  # details for debugging go to stderr


def test_prints_inside_a_command_do_not_corrupt_stdout(capsys, monkeypatch):
    class NoisyEvidenceAPI:
        def get_all_evidence(self, database_path, case_id):
            print("progress message that used to land in stdout")
            return {"success": True, "evidence": []}

    monkeypatch.setattr(main_cli, "EvidenceAPI", NoisyEvidenceAPI, raising=False)

    exit_code, result, stderr = run(capsys, "evidence", "case.db", 1)

    assert exit_code == 0
    assert result == {"success": True, "evidence": []}
    assert "progress message" in stderr


def test_payload_reporting_failure_becomes_an_error(capsys, monkeypatch):
    class MissingPreviewAPI:
        def get_preview(self, database_path, evidence_id, artifact_path):
            return {"success": False, "message": "Evidence not found."}

    monkeypatch.setattr(main_cli, "PreviewAPI", MissingPreviewAPI, raising=False)

    exit_code, result, _ = run(capsys, "preview", "case.db", 7)

    assert exit_code == main_cli.EXIT_FAILURE
    assert result["error"] == "Evidence not found."
    assert result["command"] == "preview"


def test_process_exit_code_matches_the_contract(tmp_path):
    """The real process, as the desktop app runs it, from another folder."""
    completed = subprocess.run(
        [sys.executable, str(ENGINE_DIR / "main_cli.py"), "evidence", "missing.db", "1"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert completed.returncode == 1
    result = json.loads(completed.stdout)
    assert result["success"] is False
    assert "missing.db" in result["error"]
