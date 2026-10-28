"""List and restore deleted files that NTFS still describes in the MFT."""
import hashlib
import json
import os
import re
from datetime import datetime
from pathlib import Path

from database.case_database import Database
from database.deleted_file_repository import DeletedFileRepository
from database.repository import Repository
from engine.api.case_access import validate_case_image
from engine.errors import NotFoundError, UsageError
from engine.recovery.deleted_files import (
    NO_DATA, OVERWRITTEN, PARTIAL, RECOVERABLE,
)
from engine.volume.opener import open_ntfs_volume
from engine.volume.run_stream import RunStream

DEFAULT_STATUSES = (RECOVERABLE, PARTIAL)
ALL_STATUSES = (RECOVERABLE, PARTIAL, OVERWRITTEN, NO_DATA)
COPY_CHUNK = 1024 * 1024
UNIX_EPOCH = datetime(1970, 1, 1)

_INVALID_CHARACTERS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{n}" for n in range(1, 10)), *(f"LPT{n}" for n in range(1, 10)),
}


def safe_component(name):
    """A path component that is valid on Windows and cannot escape upward."""
    name = _INVALID_CHARACTERS.sub("_", name).rstrip(" .")
    if name in ("", ".", ".."):
        name = "_"
    if name.split(".")[0].upper() in _RESERVED_NAMES:
        name = "_" + name
    return name


def relative_output_path(full_path, filename, record_number):
    """Where a deleted file goes inside the destination folder."""
    parts = [part for part in (full_path or "").replace("\\", "/").split("/") if part not in ("", ".")]
    if not parts:
        parts = [filename or f"record_{record_number}"]
    return Path(*(safe_component(part) for part in parts))


def _unique(path, record_number):
    if not path.exists():
        return path
    candidate = path.with_name(f"{path.stem} (record {record_number}){path.suffix}")
    counter = 2
    while candidate.exists():
        candidate = path.with_name(f"{path.stem} (record {record_number}-{counter}){path.suffix}")
        counter += 1
    return candidate


class DeletedFileAPI:

    def list_deleted(self, database_path, case_id, statuses=None):
        statuses = self._statuses(statuses, ALL_STATUSES)
        database = Database()
        try:
            database.open_case(database_path)
            if Repository(database).get_case(case_id) is None:
                raise NotFoundError(f"Case {case_id} was not found in the database")
            files = DeletedFileRepository(database).list_by_case(case_id, statuses)
        finally:
            database.close()

        counts = {status: 0 for status in ALL_STATUSES}
        for item in files:
            counts[item["status"]] += 1
        return {
            "success": True,
            "case_id": case_id,
            "count": len(files),
            "status_counts": counts,
            "files": files,
        }

    def recover_deleted(
        self, image_path, database_path, case_id, destination,
        statuses=None, record_numbers=None,
    ):
        """Write deleted files back to disk under their original paths."""
        if not destination or not str(destination).strip():
            raise UsageError("destination folder cannot be empty")
        statuses = self._statuses(statuses, DEFAULT_STATUSES)

        database = Database()
        try:
            database.open_case(database_path)
            validate_case_image(Repository(database), case_id, image_path)
            targets = DeletedFileRepository(database).list_by_case(
                case_id, statuses, record_numbers
            )
        finally:
            database.close()

        root = Path(destination).resolve()
        root.mkdir(parents=True, exist_ok=True)
        results = []

        with open(image_path, "rb") as image:
            parser = open_ntfs_volume(image)
            for target in targets:
                results.append(self._restore(parser, target, root))

        manifest = root / f"recovery_manifest_case{case_id}_{datetime.now():%Y%m%d_%H%M%S}.json"
        manifest.write_text(json.dumps({
            "case_id": case_id,
            "image_path": os.path.abspath(image_path),
            "created": datetime.now().isoformat(),
            "statuses": list(statuses),
            "files": results,
        }, indent=2, default=str), encoding="utf-8")

        return {
            "success": True,
            "case_id": case_id,
            "destination": str(root),
            "manifest": str(manifest),
            "recovered_count": sum(1 for item in results if "path" in item),
            "failed_count": sum(1 for item in results if "error" in item),
            "recovered_bytes": sum(item.get("size", 0) for item in results),
            "files": results,
        }

    # ------------------------------------------------------------------

    @staticmethod
    def _statuses(statuses, default):
        if not statuses:
            return default
        unknown = set(statuses) - set(ALL_STATUSES)
        if unknown:
            raise UsageError(
                f"Unknown status {sorted(unknown)}; use {', '.join(ALL_STATUSES)}"
            )
        return tuple(statuses)

    def _restore(self, parser, target, root):
        entry = {
            "record_number": target["record_number"],
            "original_path": target["full_path"],
            "status": target["status"],
        }
        try:
            evidence = parser.get_evidence(target["record_number"])
            if evidence is None or not evidence.deleted or evidence.filename != target["filename"]:
                raise ValueError(
                    "MFT record no longer describes this deleted file"
                )

            relative = relative_output_path(
                target["full_path"], target["filename"], target["record_number"]
            )
            path = _unique(root / relative, target["record_number"])
            if root not in path.resolve().parents:
                raise ValueError("refusing to write outside the destination folder")
            path.parent.mkdir(parents=True, exist_ok=True)

            digest = hashlib.sha256()
            source = RunStream.for_evidence(parser.image, parser.geometry, evidence)
            written = 0
            with open(path, "xb") as handle:  # "x": never overwrite
                while written < evidence.file_size:
                    chunk = source.read(min(COPY_CHUNK, evidence.file_size - written))
                    if not chunk:
                        break
                    handle.write(chunk)
                    digest.update(chunk)
                    written += len(chunk)

            if evidence.modified_time is not None:
                # NTFS times are UTC; convert explicitly, not as local time.
                times = [evidence.accessed_time or evidence.modified_time, evidence.modified_time]
                try:
                    os.utime(path, tuple((t - UNIX_EPOCH).total_seconds() for t in times))
                except (OverflowError, OSError, ValueError):
                    pass

            entry.update({
                "path": str(path),
                "size": written,
                "sha256": digest.hexdigest(),
                "complete": written == evidence.file_size,
            })
            if target["unreliable_ranges"]:
                # Byte ranges that hold other files' data (from analysis).
                entry["unreliable_ranges"] = target["unreliable_ranges"]
        except Exception as error:
            entry["error"] = f"{type(error).__name__}: {error}"
        return entry
