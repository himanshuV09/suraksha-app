"""Read the slack space of one file (bytes past its end, inside its clusters)."""
from database.case_database import Database
from database.mapper.evidence_mapper import EvidenceMapper
from database.repository import Repository
from engine.errors import NotFoundError
from engine.preview.preview_session import PreviewSession
from engine.recovery.file_slack import read_slack

# The UI shows slack as hex; keep the response small.
MAX_RETURNED_BYTES = 64 * 1024


class SlackAPI:

    def file_slack(self, database_path, evidence_id):
        database = Database()
        try:
            database.open_case(database_path)
            repository = Repository(database)
            row = repository.get_evidence(evidence_id)
            if row is None:
                raise NotFoundError(f"Evidence {evidence_id} was not found")
            info = EvidenceMapper.to_dict(row)
            case = repository.get_case(info["case_id"])
        finally:
            database.close()

        session = PreviewSession(case[2])
        session.open()
        try:
            evidence = session.get_evidence(info["record_number"])
            if evidence is None:
                raise NotFoundError(f"MFT record {info['record_number']} could not be read")
            slack = read_slack(
                session.image, session.parser.geometry, evidence,
                limit=MAX_RETURNED_BYTES,
            )
        finally:
            session.close()

        return {
            "success": True,
            "evidence_id": evidence_id,
            "record_number": info["record_number"],
            "filename": evidence.filename,
            "file_size": evidence.file_size,
            "resident": evidence.resident_data is not None,
            "slack_size": slack["slack_size"],
            "slack_offset": slack["offset"],
            "truncated": slack.get("truncated", False),
            "all_zero": slack.get("all_zero", True),
            "encoding": "hex",
            "data": slack["data"].hex(),
            "strings": slack["strings"],
        }
