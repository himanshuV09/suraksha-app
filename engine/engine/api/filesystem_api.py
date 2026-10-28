
from pathlib import Path

from database.case_database import Database
from database.repository import Repository
from database.mapper.filesystem_mapper import FilesystemMapper
from database.mapper.container_mapper import ContainerMapper
from filesystem_tree import build_filesystem_tree


class FilesystemAPI:

    def get_filesystem_tree(self, database_path, case_id):
        database = Database()

        try:
            database.open_case(database_path)
            repository = Repository(database)

            # Fetch the case row:
            # case_id, case_name, image_path, created_at,
            # investigator, description
            case_row = repository.get_case(case_id)

            if case_row is None:
                raise ValueError(f"Case not found: {case_id}")

            image_path = case_row[2]
            image_name = (
                Path(image_path).name
                if image_path
                else case_row[1]
            )

            rows = repository.get_evidence_tree(case_id)
            evidence = FilesystemMapper.to_object_list(rows)

            artifact_rows = repository.get_container_artifacts(
                case_id
            )
            artifacts = ContainerMapper.to_object_list(
                artifact_rows
            )

            evidence_database = {
                item.record_number: item
                for item in evidence
            }

            for artifact in artifacts:
                parent = evidence_database.get(
                    artifact.parent_record
                )

                if parent:
                    parent.children.append(artifact)

            # Load real regions for this case and evidence image.
            unallocated_regions = []

            if image_path:
                unallocated_regions = (
                    repository.get_unallocated_regions(
                        case_id,
                        image_path,
                    )
                )

            tree = build_filesystem_tree(
                evidence_database,
                image_name=image_name,
                unallocated_regions=unallocated_regions,
            )

            return {
                "success": True,
                "case_id": case_id,
                "tree": tree,
            }

        finally:
            database.close()
