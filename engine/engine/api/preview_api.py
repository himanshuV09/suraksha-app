from database.case_database import Database
from database.repository import Repository
from database.mapper.evidence_mapper import EvidenceMapper
from database.mapper.container_mapper import ContainerMapper
from engine.preview.container_preview_service import ContainerPreviewService


from engine.preview.preview_session import PreviewSession
from engine.preview.recovery_service import RecoveryService
from engine.preview.preview_builder import PreviewBuilder


class PreviewAPI:

    def get_preview(
        self,
        database_path: str,
        evidence_id: int,
        artifact_path: str = None,
    ):

        database = Database()

        try:

            #
            # Open case database
            #
            database.open_case(database_path)

            repository = Repository(database)

            #
            # Get selected evidence
            #
            evidence_row = repository.get_evidence(
                evidence_id
            )

            if evidence_row is None:

                return {
                    "success": False,
                    "message": "Evidence not found."
                }

            evidence_info = EvidenceMapper.to_dict(
                evidence_row
            )

            #
            # Get case
            #
            case_row = repository.get_case(
                evidence_info["case_id"]
            )

            if case_row is None:

                return {
                    "success": False,
                    "message": "Case not found."
                }

            image_path = case_row[2]

            #
            # Open image
            #
            session = PreviewSession(
                image_path
            )

            session.open()

            try:

                #
                # Parse ONE MFT record
                #
                evidence = session.get_evidence(
                    evidence_info["record_number"]
                )

                if evidence is None:

                    return {
                        "success": False,
                        "message": "Unable to parse record."
                    }

                #
                # Normal NTFS preview
                #
                if artifact_path is None:

                    data = RecoveryService().recover(
                        session.image_reader,
                        evidence
                    )

                    return PreviewBuilder().build(
                        evidence,
                        data
                    )

                #
                # Container preview
                #
                artifact_row = repository.get_container_artifact(
                    evidence.record_number,
                    artifact_path
                )

                if artifact_row is None:

                    return {
                        "success": False,
                        "message": "Container artifact not found."
                    }

                artifact = ContainerMapper.to_object(
                    artifact_row
                )

                data = ContainerPreviewService().recover_artifact(
                    session.image_reader,
                    evidence,
                    artifact.path
                )

                #
                # Adapt artifact for PreviewBuilder
                #
                artifact.filename = artifact.name
                artifact.file_size = artifact.size

                return PreviewBuilder().build(
                    artifact,
                    data
                )

            finally:

                session.close()

        finally:

            database.close()