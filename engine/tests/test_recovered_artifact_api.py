
from unittest.mock import Mock, patch

import pytest

from engine.api.recovered_artifact_api import RecoveredArtifactAPI

from engine.allocation.recovered_artifact_metadata import (
    RecoveredArtifactMetadata,
)


@pytest.fixture
def database():
    db = Mock()
    db.cursor = Mock()
    return db


def test_returns_empty_artifact_list(database):
    repository = Mock()
    repository.list_by_case.return_value = []

    with (
        patch(
            "engine.api.recovered_artifact_api.Database",
            return_value=database,
        ),
        patch(
            "engine.api.recovered_artifact_api.RecoveredArtifactRepository",
            return_value=repository,
        ),
    ):
        api = RecoveredArtifactAPI()
        result = api.get_recovered_artifacts("case.db", 1)

    assert result == {
        "success": True,
        "case_id": 1,
        "count": 0,
        "artifacts": [],
    }
    repository.list_by_case.assert_called_once_with(1)
    database.open_case.assert_called_once_with("case.db")
    database.close.assert_called_once()


@pytest.mark.parametrize("case_id", [0, -1])
def test_rejects_non_positive_case_id(case_id):
    api = RecoveredArtifactAPI()

    with pytest.raises(ValueError):
        api.get_recovered_artifacts("case.db", case_id)


@pytest.mark.parametrize("case_id", ["1", None, 1.5])
def test_rejects_non_integer_case_id(case_id):
    api = RecoveredArtifactAPI()

    with pytest.raises(TypeError):
        api.get_recovered_artifacts("case.db", case_id)


def test_closes_database_when_repository_fails(database):
    repository = Mock()
    repository.list_by_case.side_effect = RuntimeError(
        "Repository failure"
    )

    with (
        patch(
            "engine.api.recovered_artifact_api.Database",
            return_value=database,
        ),
        patch(
            "engine.api.recovered_artifact_api.RecoveredArtifactRepository",
            return_value=repository,
        ),
    ):
        api = RecoveredArtifactAPI()

        with pytest.raises(RuntimeError, match="Repository failure"):
            api.get_recovered_artifacts("case.db", 1)

    database.close.assert_called_once()

def test_serializes_recovered_artifact_metadata(database):
    metadata = RecoveredArtifactMetadata(
        artifact_id=7,
        signature="JPEG",
        extension=".jpg",
        size=8154131,
        sha256="a" * 64,
        confidence=0.5,
        source_image="test.001",
        source_type="UNALLOCATED",
        region_start_cluster=167186,
        region_end_cluster=259984,
        region_start_offset=684793856,
        source_offset=741667563,
        relative_offset=56873707,
        start_cluster=181071,
        end_cluster=183061,
        validation_reason="JPEG structural validation passed",
    )

    repository = Mock()
    repository.list_by_case.return_value = [metadata]

    with (
        patch(
            "engine.api.recovered_artifact_api.Database",
            return_value=database,
        ),
        patch(
            "engine.api.recovered_artifact_api.RecoveredArtifactRepository",
            return_value=repository,
        ),
    ):
        result = RecoveredArtifactAPI().get_recovered_artifacts(
            "case.db", 1
        )

    assert result["success"] is True
    assert result["count"] == 1
    assert result["artifacts"][0]["artifact_id"] == 7
    assert result["artifacts"][0]["sha256"] == "a" * 64
    assert result["artifacts"][0]["source_type"] == "UNALLOCATED"
    assert result["artifacts"][0]["source_offset"] == 741667563
    assert result["artifacts"][0]["start_cluster"] == 181071
    assert result["artifacts"][0]["end_cluster"] == 183061
    assert result["artifacts"][0]["validation_reason"] == (
        "JPEG structural validation passed"
    )


def test_serializes_multiple_artifacts_in_repository_order(database):
    first = RecoveredArtifactMetadata(
        artifact_id=3,
        signature="JPEG",
        extension=".jpg",
        size=100,
        sha256="b" * 64,
        confidence=0.5,
        source_image="test.001",
        source_type="UNALLOCATED",
        region_start_cluster=10,
        region_end_cluster=20,
        region_start_offset=40960,
        source_offset=41000,
        relative_offset=40,
        start_cluster=10,
        end_cluster=10,
        validation_reason="JPEG structural validation passed",
    )

    second = RecoveredArtifactMetadata(
        artifact_id=8,
        signature="JPEG",
        extension=".jpg",
        size=200,
        sha256="c" * 64,
        confidence=0.5,
        source_image="test.001",
        source_type="UNALLOCATED",
        region_start_cluster=30,
        region_end_cluster=40,
        region_start_offset=122880,
        source_offset=123000,
        relative_offset=120,
        start_cluster=30,
        end_cluster=30,
        validation_reason="JPEG structural validation passed",
    )

    repository = Mock()
    repository.list_by_case.return_value = [first, second]

    with (
        patch(
            "engine.api.recovered_artifact_api.Database",
            return_value=database,
        ),
        patch(
            "engine.api.recovered_artifact_api.RecoveredArtifactRepository",
            return_value=repository,
        ),
    ):
        result = RecoveredArtifactAPI().get_recovered_artifacts(
            "case.db", 1
        )

    assert result["count"] == 2
    assert [
        item["artifact_id"] for item in result["artifacts"]
    ] == [3, 8]
