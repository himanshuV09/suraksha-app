
import json
import sys

import main_cli


def test_recovered_artifacts_command_returns_json(
    monkeypatch, capsys
):
    expected = {
        "success": True,
        "case_id": 4,
        "count": 1,
        "artifacts": [
            {
                "artifact_id": 12,
                "signature": "JPEG",
                "extension": ".jpg",
                "size": 100,
                "sha256": "a" * 64,
                "source_type": "UNALLOCATED",
                "source_offset": 41000,
            }
        ],
    }

    class FakeRecoveredArtifactAPI:
        def get_recovered_artifacts(
            self, database_path, case_id
        ):
            assert database_path == "case.db"
            assert case_id == 4
            return expected

    monkeypatch.setattr(
        main_cli,
        "RecoveredArtifactAPI",
        FakeRecoveredArtifactAPI,
        raising=False,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["main_cli.py", "recovered-artifacts", "case.db", "4"],
    )

    main_cli.main()

    result = json.loads(capsys.readouterr().out)
    assert result == expected


def test_recovered_artifacts_command_rejects_wrong_arguments(
    monkeypatch, capsys
):
    monkeypatch.setattr(
        sys,
        "argv",
        ["main_cli.py", "recovered-artifacts", "case.db"],
    )

    main_cli.main()

    result = json.loads(capsys.readouterr().out)
    assert result["success"] is False
    assert "Usage" in result["error"]
