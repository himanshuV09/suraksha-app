
from database.case_database import Database
from database.schema import DatabaseSchema
from engine.api.recovered_artifact_api import RecoveredArtifactAPI


def test_api_returns_persisted_recovered_artifact(tmp_path):
    database_path = tmp_path / "integration_case.db"

    # Create a real temporary case database and schema.
    database = Database()
    database.open_case_for_test = None  # No production API changes needed.

    import sqlite3

    connection = sqlite3.connect(database_path)
    try:
        database.connection = connection
        database.cursor = connection.cursor()

        DatabaseSchema(database).create_schema()

        database.cursor.execute(
            """
            INSERT INTO cases (
                case_name, image_path, investigator, description
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                "Integration Case",
                "test.001",
                "Test Investigator",
                "API integration test",
            ),
        )
        case_id = database.cursor.lastrowid

        database.cursor.execute(
            """
            INSERT INTO recovered_artifacts (
                case_id, signature, extension, size, sha256,
                confidence, source_image, source_type,
                region_start_cluster, region_end_cluster,
                region_start_offset, source_offset, relative_offset,
                start_cluster, end_cluster, validation_reason
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                case_id, "JPEG", ".jpg", 100, "a" * 64,
                0.9, "test.001", "UNALLOCATED",
                10, 20, 40960, 41000, 40,
                10, 10, "JPEG structural validation passed",
            ),
        )
        database.commit()
    finally:
        database.close()

    result = RecoveredArtifactAPI().get_recovered_artifacts(
        str(database_path), case_id
    )

    assert result["success"] is True
    assert result["case_id"] == case_id
    assert result["count"] == 1

    artifact = result["artifacts"][0]
    assert artifact["artifact_id"] == 1
    assert artifact["signature"] == "JPEG"
    assert artifact["extension"] == ".jpg"
    assert artifact["size"] == 100
    assert artifact["sha256"] == "a" * 64
    assert artifact["source_type"] == "UNALLOCATED"
    assert artifact["source_offset"] == 41000
    assert artifact["relative_offset"] == 40
    assert artifact["validation_reason"] == (
        "JPEG structural validation passed"
    )
