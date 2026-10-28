"""Application-facing API for NTFS metafiles."""
import os

from database.case_database import Database
from database.metafile_repository import MetafileRepository
from database.repository import Repository
from engine.api.case_access import validate_case_image
from engine.errors import NotFoundError, UsageError
from engine.metafiles.analyzer import export_metafiles
from engine.volume.opener import open_ntfs_volume


class MetafileAPI:

    def list_metafiles(self, database_path, case_id):
        """The metafile summary stored when the case was analyzed."""
        database = Database()
        try:
            database.open_case(database_path)
            if Repository(database).get_case(case_id) is None:
                raise NotFoundError(f"Case {case_id} was not found in the database")
            metafiles = MetafileRepository(database).list_by_case(case_id)
        finally:
            database.close()

        return {
            "success": True,
            "case_id": case_id,
            "count": len(metafiles),
            "metafiles": metafiles,
        }

    def extract_metafiles(self, image_path, database_path, case_id, destination):
        """Copy the raw metafile streams of the case's image to a folder."""
        if not destination or not str(destination).strip():
            raise UsageError("destination folder cannot be empty")

        database = Database()
        try:
            database.open_case(database_path)
            validate_case_image(Repository(database), case_id, image_path)
        finally:
            database.close()

        destination = os.path.abspath(destination)
        with open(image_path, "rb") as image:
            exported = export_metafiles(open_ntfs_volume(image), destination)

        return {
            "success": True,
            "case_id": case_id,
            "destination": destination,
            "exported_count": sum(1 for item in exported if "path" in item),
            "skipped_count": sum(1 for item in exported if "skipped" in item),
            "failed_count": sum(1 for item in exported if "error" in item),
            "files": exported,
        }
