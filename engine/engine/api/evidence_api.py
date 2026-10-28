from database.case_database import Database
from database.repository import Repository

from database.mapper.evidence_mapper import (
    EvidenceMapper,
)


class EvidenceAPI:

    def get_all_evidence(
        self,
        database_path,
        case_id
    ):

        database = Database()

        try:

            database.open_case(
                database_path
            )

            repository = Repository(
                database
            )

            rows = repository.get_all_evidence(
                case_id
            )

            evidence = (
                EvidenceMapper.to_dict_list(
                    rows
                )
            )

            return {

                "success": True,

                "case_id": case_id,

                "count": len(evidence),

                "evidence": evidence,

            }

        finally:

            database.close()