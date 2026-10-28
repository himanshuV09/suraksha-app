import io
import mimetypes
import os
import zipfile

from .base_parser import BaseContainerParser


class ZipParser(BaseContainerParser):
    """Lists the members of ZIP-based containers (ZIP, Office, APK, ...)."""

    SUPPORTED = {
        ".zip",
        ".docx",
        ".pptx",
        ".xlsx",
        ".apk",
        ".jar",
        ".odt",
        ".ods",
        ".epub",
    }

    def supports(self, evidence):

        if not evidence.filename:
            return False

        return evidence.filename.lower().endswith(tuple(self.SUPPORTED))

    def parse(self, evidence, source):
        """List members of the archive in ``source`` (file object or bytes).

        With a seekable file object only the archive's central directory
        is read, not the member data.
        """
        if isinstance(source, (bytes, bytearray)):
            source = io.BytesIO(source)

        try:
            archive = zipfile.ZipFile(source)
        except (zipfile.BadZipFile, OSError, ValueError):
            return []

        with archive:
            children = [self._describe(entry) for entry in archive.infolist()]

        # Add folders that are implied by member paths but not listed.
        listed = {child["path"] for child in children if child["directory"]}
        implied = set()
        for child in children:
            parts = child["path"].split("/")[:-1]
            for depth in range(1, len(parts) + 1):
                folder = "/".join(parts[:depth])
                if folder not in listed:
                    implied.add(folder)

        children += [
            {
                "name": os.path.basename(folder),
                "path": folder,
                "directory": True,
                "size": 0,
                "mime_type": None,
            }
            for folder in sorted(implied)
        ]

        children.sort(key=lambda item: (not item["directory"], item["path"].lower()))

        return children

    @staticmethod
    def _describe(entry):
        mime_type = None
        if not entry.is_dir():
            mime_type = (
                mimetypes.guess_type(entry.filename)[0]
                or "application/octet-stream"
            )
        path = entry.filename.rstrip("/")
        return {
            "name": os.path.basename(path),
            "path": path,
            "directory": entry.is_dir(),
            "size": entry.file_size,
            "mime_type": mime_type,
        }
