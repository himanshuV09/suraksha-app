import hashlib
import pytest

from database.case_database import Database
from database.recovered_artifact_repository import (
    RecoveredArtifactRepository,
)
from engine.allocation.artifact_provenance import ArtifactProvenance
from engine.allocation.carved_artifact import CarvedArtifact
from engine.allocation.recovered_artifact_record import (
    RecoveredArtifactRecord,
)
from engine.allocation.carving_models import SignatureCandidate
from engine.allocation.validated_candidate import ValidatedCandidate

from engine.allocation.recovered_artifact_metadata import (
    RecoveredArtifactMetadata,
)

def create_database(tmp_path):
    database = Database()

    database.create_case(
        "repository_test",
        directory=str(tmp_path),
    )

    from database.schema import DatabaseSchema

    schema = DatabaseSchema(database)
    schema.create_schema()

    cursor = database.cursor

    cursor.execute(
        """
        INSERT INTO cases (
            case_name,
            image_path,
            created_at,
            investigator,
            description
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            "repository_test",
            "test.001",
            "2026-01-01T00:00:00",
            "Test Investigator",
            "Repository test case",
        ),
    )

    database.commit()

    case_id = cursor.lastrowid

    return database, case_id


def create_record():
    candidate = SignatureCandidate(
        signature="JPEG",
        extension=".jpg",
        offset=684794112,
        relative_offset=256,
        start_cluster=167186,
        end_cluster=259984,
        confidence=0.95,
    )

    validated_candidate = ValidatedCandidate(
        candidate=candidate,
        detected_size=9,
        validation_reason="JPEG structural validation passed",
    )

    data = (
        b"\xFF\xD8\xFF"
        b"\xE0\x00\x10\x00"
        b"\xFF\xD9"
    )

    artifact = CarvedArtifact(
        candidate=validated_candidate,
        data=data,
        source_offset=684794112,
        size=len(data),
    )

    provenance = ArtifactProvenance(
        source_image="test.001",
        source_type="UNALLOCATED",
        region_start_cluster=167186,
        region_end_cluster=259984,
        region_start_offset=684793856,
        source_offset=684794112,
        relative_offset=256,
        start_cluster=167186,
        end_cluster=167186,
    )

    sha256 = hashlib.sha256(data).hexdigest()

    return RecoveredArtifactRecord(
        artifact=artifact,
        sha256=sha256,
        provenance=provenance,
    )


def test_create_persists_recovered_artifact(tmp_path):
    database, case_id = create_database(tmp_path)

    repository = RecoveredArtifactRepository(database)

    record = create_record()

    artifact_id = repository.create(
        case_id=case_id,
        record=record,
    )

    assert isinstance(artifact_id, int)
    assert artifact_id > 0

    cursor = database.cursor

    cursor.execute(
        """
        SELECT
            case_id,
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
        FROM recovered_artifacts
        WHERE artifact_id = ?
        """,
        (artifact_id,),
    )

    row = cursor.fetchone()

    assert row is not None

    assert row[0] == case_id
    assert row[1] == "JPEG"
    assert row[2] == ".jpg"
    assert row[3] == 9
    assert row[4] == record.sha256
    assert row[5] == 0.95
    assert row[6] == "test.001"
    assert row[7] == "UNALLOCATED"
    assert row[8] == 167186
    assert row[9] == 259984
    assert row[10] == 684793856
    assert row[11] == 684794112
    assert row[12] == 256
    assert row[13] == 167186
    assert row[14] == 167186
    assert row[15] == "JPEG structural validation passed"

    database.close()

def test_get_reconstructs_recovered_artifact_metadata(tmp_path):
    database, case_id = create_database(tmp_path)

    repository = RecoveredArtifactRepository(database)

    original = create_record()

    artifact_id = repository.create(
        case_id=case_id,
        record=original,
    )

    restored = repository.get(artifact_id)

    assert isinstance(
        restored,
        RecoveredArtifactMetadata,
    )

    assert restored.signature == original.signature
    assert restored.extension == original.extension
    assert restored.size == original.size
    assert restored.sha256 == original.sha256
    assert restored.confidence == original.confidence

    assert restored.source_image == (
        original.provenance.source_image
    )

    assert restored.source_type == (
        original.provenance.source_type
    )

    assert restored.region_start_cluster == (
        original.provenance.region_start_cluster
    )

    assert restored.region_end_cluster == (
        original.provenance.region_end_cluster
    )

    assert restored.region_start_offset == (
        original.provenance.region_start_offset
    )

    assert restored.source_offset == (
        original.provenance.source_offset
    )

    assert restored.relative_offset == (
        original.provenance.relative_offset
    )

    assert restored.start_cluster == (
        original.provenance.start_cluster
    )

    assert restored.end_cluster == (
        original.provenance.end_cluster
    )

    assert restored.validation_reason == (
        original.artifact.candidate.validation_reason
    )

    database.close()

def test_get_rejects_invalid_artifact_id(tmp_path):
    database, case_id = create_database(tmp_path)

    repository = RecoveredArtifactRepository(database)

    with pytest.raises(ValueError):
        repository.get(0)

    with pytest.raises(ValueError):
        repository.get(-1)

    database.close()

def test_get_rejects_missing_artifact(tmp_path):
    database, case_id = create_database(tmp_path)

    repository = RecoveredArtifactRepository(database)

    with pytest.raises(KeyError):
        repository.get(999999)

    database.close()

def test_list_by_case_returns_recovered_artifact_metadata(tmp_path):
    database, case_id = create_database(tmp_path)

    repository = RecoveredArtifactRepository(database)

    first = create_record()
    second = create_record()

    first_id = repository.create(
        case_id=case_id,
        record=first,
    )

    second_id = repository.create(
        case_id=case_id,
        record=second,
    )

    results = repository.list_by_case(case_id)

    assert isinstance(results, list)
    assert len(results) == 2

    assert all(
        isinstance(
            item,
            RecoveredArtifactMetadata,
        )
        for item in results
    )

    assert results[0].signature == first.signature
    assert results[0].source_offset == first.provenance.source_offset

    assert results[1].signature == second.signature
    assert results[1].source_offset == second.provenance.source_offset

    database.close()

def test_list_by_case_isolates_artifacts_between_cases(tmp_path):
    database = Database()

    database.create_case(
        "repository_test",
        directory=str(tmp_path),
    )

    from database.schema import DatabaseSchema

    schema = DatabaseSchema(database)
    schema.create_schema()

    cursor = database.cursor

    cursor.execute(
        """
        INSERT INTO cases (
            case_name,
            image_path,
            created_at,
            investigator,
            description
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            "case_one",
            "case_one.001",
            "2026-01-01T00:00:00",
            "Test Investigator",
            "First test case",
        ),
    )

    case_one_id = cursor.lastrowid

    cursor.execute(
        """
        INSERT INTO cases (
            case_name,
            image_path,
            created_at,
            investigator,
            description
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            "case_two",
            "case_two.001",
            "2026-01-01T00:00:00",
            "Test Investigator",
            "Second test case",
        ),
    )

    case_two_id = cursor.lastrowid

    database.commit()

    repository = RecoveredArtifactRepository(database)

    artifact = create_record()

    repository.create(
        case_id=case_one_id,
        record=artifact,
    )

    results_case_one = repository.list_by_case(
        case_one_id,
    )

    results_case_two = repository.list_by_case(
        case_two_id,
    )

    assert len(results_case_one) == 1
    assert len(results_case_two) == 0

    assert (
        results_case_one[0].source_image
        == artifact.provenance.source_image
    )

    database.close()