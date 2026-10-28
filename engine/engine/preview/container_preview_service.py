import zipfile

from engine.volume.run_stream import RunStream


class ContainerPreviewService:

    def recover_artifact(
        self,
        image_reader,
        evidence,
        artifact_path
    ):
        """
        Extract one member of a ZIP-based container
        (DOCX, PPTX, XLSX, APK, JAR, ZIP, etc.)

        Only the archive's central directory and the requested member
        are read from the image, not the whole container.

        Parameters
        ----------
        image_reader : ImageReader
            Active image reader.

        evidence : Evidence
            Parent NTFS evidence object (e.g. Report.docx).

        artifact_path : str
            Internal path inside the archive
            (e.g. 'word/media/image1.jpeg').

        Returns
        -------
        bytes
            Extracted file bytes.

        Raises
        ------
        FileNotFoundError
            If the requested file does not exist.

        zipfile.BadZipFile
            If the parent file is not a valid ZIP archive.
        """

        if not evidence.file_size:
            raise ValueError("Unable to recover parent container.")

        stream = RunStream.for_evidence(
            image_reader.image, image_reader.geometry, evidence
        )

        with zipfile.ZipFile(stream) as archive:

            normalized = artifact_path.replace("\\", "/")

            if normalized not in archive.namelist():
                raise FileNotFoundError(normalized)

            return archive.read(normalized)
