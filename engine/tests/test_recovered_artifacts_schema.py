import sqlite3

from database.case_database import Database
from database.schema import DatabaseSchema


def create_database(tmp_path):
    database = Database()

    database.create_case(
        "schema_test",
        directory=str(tmp_path),
    )

    schema = DatabaseSchema(database)
    schema.create_schema()

    return database


def test_recovered_artifacts_table_exists(tmp_path):
    database = create_database(tmp_path)

    cursor = database.cursor

    cursor.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name = 'recovered_artifacts'
        """
    )

    row = cursor.fetchone()

    assert row is not None
    assert row[0] == "recovered_artifacts"

    database.close()


def test_recovered_artifacts_schema_contains_expected_columns(tmp_path):
    database = create_database(tmp_path)

    cursor = database.cursor

    cursor.execute(
        "PRAGMA table_info(recovered_artifacts)"
    )

    columns = {
        row[1]
        for row in cursor.fetchall()
    }

    expected_columns = {
        "artifact_id",
        "case_id",
        "signature",
        "extension",
        "size",
        "sha256",
        "confidence",
        "source_image",
        "source_type",
        "region_start_cluster",
        "region_end_cluster",
        "region_start_offset",
        "source_offset",
        "relative_offset",
        "start_cluster",
        "end_cluster",
        "validation_reason",
        "fragments",  # pieces of a file reassembled from free space
    }

    assert columns == expected_columns

    database.close()


def test_recovered_artifacts_requires_case_id(tmp_path):
    database = create_database(tmp_path)

    cursor = database.cursor

    try:
        cursor.execute(
            """
            INSERT INTO recovered_artifacts (
                signature,
                extension,
                size,
                sha256,
                confidence,
                source_image,
                source_type,
                region_start_cluster,
                region_end_cluster,
                region_start_offset,
                source_offset,
                relative_offset,
                start_cluster,
                end_cluster,
                validation_reason
            )
            VALUES (
                'JPEG',
                '.jpg',
                9,
                'a' || printf('%063d', 0),
                0.95,
                'test.001',
                'UNALLOCATED',
                167186,
                259984,
                684793856,
                684794112,
                256,
                167186,
                167186,
                'JPEG structural validation passed'
            )
            """
        )

        assert False, "Insert without case_id should fail"

    except sqlite3.IntegrityError:
        pass

    database.close()