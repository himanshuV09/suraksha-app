import hashlib
import json
import os
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from database.case_database import Database
from database.recovered_artifact_repository import (
    RecoveredArtifactRepository,
)
from database.repository import Repository
from engine.api.case_access import validate_case_image
from engine.errors import NotFoundError, UsageError

# Previews return the file inline (base64); keep them bounded.
MAX_PREVIEW_SIZE = 64 * 1024 * 1024


def artifact_filename(artifact):
    """Name for a carved file: recovered_<id>_<offset>.<ext>."""
    extension = artifact.extension if artifact.extension.startswith(".") else f".{artifact.extension}"
    return f"recovered_{artifact.artifact_id}_{artifact.source_offset}{extension}"


class RecoveredArtifactAPI:
    """Application-facing API for persisted recovered artifacts."""

    def get_recovered_artifacts(self, database_path, case_id):
        if not isinstance(case_id, int) or isinstance(case_id, bool):
            raise TypeError("case_id must be an integer")

        if case_id <= 0:
            raise ValueError("case_id must be greater than zero")

        if not isinstance(database_path, str):
            raise TypeError("database_path must be a string")

        if not database_path.strip():
            raise ValueError("database_path cannot be empty")

        database = Database()

        try:
            database.open_case(database_path)

            repository = RecoveredArtifactRepository(database)
            records = repository.list_by_case(case_id)

            artifacts = [asdict(record) for record in records]

            return {
                "success": True,
                "case_id": case_id,
                "count": len(artifacts),
                "artifacts": artifacts,
            }
        finally:
            database.close()

    # ------------------------------------------------------------------
    # Reading carved files back from the image
    # ------------------------------------------------------------------

    def preview(self, image_path, database_path, case_id, artifact_id):
        """Preview one carved file, re-checking its stored SHA-256."""
        from engine.preview.preview_builder import PreviewBuilder

        artifact = self._artifacts(image_path, database_path, case_id, [artifact_id])[0]
        if artifact.size > MAX_PREVIEW_SIZE:
            raise UsageError(
                f"Recovered file is {artifact.size} bytes; export it instead "
                f"(preview limit {MAX_PREVIEW_SIZE} bytes)"
            )

        with open(image_path, "rb") as image:
            data = self._read(image, artifact)

        preview = PreviewBuilder().build(
            SimpleNamespace(filename=artifact_filename(artifact), file_size=artifact.size),
            data,
        )
        preview.update({
            "artifact_id": artifact.artifact_id,
            "sha256": artifact.sha256,
            "hash_verified": hashlib.sha256(data).hexdigest() == artifact.sha256,
        })
        return preview

    def export(self, image_path, database_path, case_id, destination, artifact_ids=None):
        """Write carved files to ``destination`` with a hash manifest."""
        if not destination or not str(destination).strip():
            raise UsageError("destination folder cannot be empty")

        artifacts = self._artifacts(image_path, database_path, case_id, artifact_ids)
        root = Path(destination).resolve()
        root.mkdir(parents=True, exist_ok=True)

        files = []
        with open(image_path, "rb") as image:
            for artifact in artifacts:
                entry = {
                    "artifact_id": artifact.artifact_id,
                    "signature": artifact.signature,
                    "source_offset": artifact.source_offset,
                    "expected_sha256": artifact.sha256,
                }
                try:
                    data = self._read(image, artifact)
                    path = root / artifact_filename(artifact)
                    with open(path, "xb") as handle:  # never overwrite
                        handle.write(data)
                    digest = hashlib.sha256(data).hexdigest()
                    entry.update({
                        "path": str(path),
                        "size": len(data),
                        "sha256": digest,
                        "hash_verified": digest == artifact.sha256,
                    })
                except Exception as error:
                    entry["error"] = f"{type(error).__name__}: {error}"
                files.append(entry)

        manifest = root / f"carved_manifest_case{case_id}_{datetime.now():%Y%m%d_%H%M%S}.json"
        manifest.write_text(json.dumps({
            "case_id": case_id,
            "image_path": os.path.abspath(image_path),
            "created": datetime.now().isoformat(),
            "files": files,
        }, indent=2), encoding="utf-8")

        return {
            "success": True,
            "case_id": case_id,
            "destination": str(root),
            "manifest": str(manifest),
            "exported_count": sum(1 for item in files if "path" in item),
            "failed_count": sum(1 for item in files if "error" in item),
            "hash_mismatches": sum(1 for item in files if item.get("hash_verified") is False),
            "files": files,
        }

    # ------------------------------------------------------------------

    @staticmethod
    def _artifacts(image_path, database_path, case_id, artifact_ids):
        database = Database()
        try:
            database.open_case(database_path)
            validate_case_image(Repository(database), case_id, image_path)
            artifacts = RecoveredArtifactRepository(database).list_by_case(case_id)
        finally:
            database.close()

        if artifact_ids:
            wanted = set(artifact_ids)
            artifacts = [item for item in artifacts if item.artifact_id in wanted]
            missing = wanted - {item.artifact_id for item in artifacts}
            if missing:
                raise NotFoundError(
                    f"Recovered artifact(s) {sorted(missing)} not found in case {case_id}"
                )
        return artifacts

    @staticmethod
    def _read(image, artifact):
        # Reassembled files list their pieces; others are one run.
        pieces = artifact.fragments or [(artifact.source_offset, artifact.size)]
        data = bytearray()
        for offset, length in pieces:
            image.seek(offset)
            data += image.read(length)
        if len(data) != artifact.size:
            raise IOError("Short read: the image is smaller than recorded")
        return bytes(data)
