class Repository:

    def __init__(self, database):

        self.database = database

        self.connection = database.connection

        self.cursor = database.cursor
    
    def _execute(
            self,
            query,
            parameters=()
    ):
        
        self.cursor.execute(
            query,
            parameters
        )
    
    def save(self):

        self.database.commit()
    
    def insert_case(
            self,
            case
    ):
        self._execute(
            """
            INSERT INTO cases 
            (
                case_name,
                image_path,
                created_at,
                investigator,
                description,
                status,
                engine_version
            )
            
            VALUES
            (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                case.case_name,
                case.image_path,
                # Stored as ISO text, the same format sqlite3's (deprecated)
                # implicit datetime adapter produced.
                case.created_at.isoformat(" ")
                if hasattr(case.created_at, "isoformat")
                else case.created_at,
                case.investigator,
                case.description,
                getattr(case, "status", "complete"),
                getattr(case, "engine_version", None),
            )
        )

        self.save()
        return self.cursor.lastrowid

    def set_case_status(self, case_id, status):
        """Mark a case "complete" or "failed" when its analysis ends."""
        from datetime import datetime

        self._execute(
            "UPDATE cases SET status = ?, completed_at = ? WHERE case_id = ?",
            (status, datetime.now().isoformat(" "), case_id),
        )
        self.save()
    
    def fetch_one(self):
        row = self.cursor.fetchone()
        return row
    
    def fetch_all(self):
        rows = self.cursor.fetchall()
        return rows
    
    def _execute_many(
            self,
            query,
            parameters
    ):
        
        self.cursor.executemany(
            query,
            parameters
        )
    
    def _map_evidence(
            self,
            case_id,
            evidence
    ):
        return (
            case_id,
            evidence.record_number,
            evidence.parent_record,
            evidence.filename,
            evidence.full_path,
            evidence.file_size,
            evidence.allocated_size,
            evidence.slack_space,
            # getattr(evidence, "slack_entropy", None),
            evidence.slack_entropy,
            evidence.fragment_count,
            int(evidence.fragmented),
            evidence.fragment_ratio,
            int(evidence.deleted),
            int(evidence.directory),
            evidence.risk_score,
            evidence.record_type
        )
    
    def _map_container_artifact(
        self,
        case_id,
        parent_record,
        artifact
    ):
        return (
            case_id,
            parent_record,
            artifact["path"],
            artifact["name"],
            int(artifact["directory"]),
            artifact["size"],
            artifact.get("mime_type"),
        )

    def _map_timeline_event(
        self,
        case_id,
        event
    ):

        return (

            case_id,

            event.record_number,

            event.filename,

            event.full_path,

            event.timestamp.isoformat(),

            event.event_type,

            int(event.deleted),

            int(event.directory),

            event.source,

            event.artifact_type,

            event.description,

        )
    
    EVIDENCE_INSERT = """
            INSERT INTO evidence 
            (
                case_id,
                record_number,
                parent_record,
                filename,
                full_path,
                file_size,
                allocated_size,
                slack_space,
                slack_entropy,
                fragment_count,
                fragmented,
                fragment_ratio,
                deleted,
                directory,
                risk_score,
                record_type
            )

            VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """

    CONTAINER_ARTIFACT_INSERT = """
            INSERT INTO container_artifacts
            (
                case_id,
                parent_record,
                path,
                name,
                directory,
                size,
                mime_type
            )

            VALUES
            (?, ?, ?, ?, ?, ?, ?)
            """

    def insert_evidence(
            self,
            case_id,
            evidence
    ):
        self.insert_evidence_many(case_id, [evidence])

    def insert_evidence_many(
            self,
            case_id,
            evidence_objects
    ):
        """Insert many evidence rows in one transaction (one commit)."""
        self._execute_many(
            self.EVIDENCE_INSERT,
            [self._map_evidence(case_id, evidence) for evidence in evidence_objects],
        )

        self.save()

    def insert_container_artifact(
        self,
        case_id,
        parent_record,
        artifact
    ):
        self.insert_container_artifacts(case_id, [(parent_record, artifact)])

    def insert_container_artifacts(
        self,
        case_id,
        items
    ):
        """Insert (parent_record, artifact) pairs in one transaction."""
        if not items:
            return

        self._execute_many(
            self.CONTAINER_ARTIFACT_INSERT,
            [
                self._map_container_artifact(case_id, parent_record, artifact)
                for parent_record, artifact in items
            ],
        )

        self.save()

    def insert_timeline_events(
        self,
        case_id,
        timeline_events
    ):

        if not timeline_events:

            return

        parameters = [

            self._map_timeline_event(

                case_id,

                event

            )

            for event in timeline_events

        ]

        self._execute_many(

            """
            INSERT INTO timeline_events
            (

                case_id,

                record_number,

                filename,

                full_path,

                timestamp,

                event_type,

                deleted,

                directory,

                source,

                artifact_type,

                description

            )

            VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,

            parameters

        )

        self.save()
    
    def _query(
            self,
            query,
            parameters = ()
    ):
        self._execute(
            query,
            parameters
        )

        return self.cursor
    
    def get_case(
            self,
            case_id
    ):
        self._query(
            """
            SELECT *
            FROM cases
            WHERE case_id = ?
            """,
            (case_id,)
        )

        return self.fetch_one()
    
    def get_all_cases(self):

        self._query(
            """
            SELECT *
            FROM cases
            ORDER BY created_at
            """
        )

        return self.fetch_all()

    def get_evidence(
            self,
            evidence_id
    ):
        self._query(
            """
            SELECT *
            FROM evidence
            WHERE evidence_id = ?
            """,
            (evidence_id,)
        )

        return self.fetch_one()


    def get_evidence_by_record(
        self,
        case_id,
        record_number
    ):

        self._query(
            """
            SELECT *

            FROM evidence

            WHERE case_id = ?
            AND record_number = ?
            """,
            (
                case_id,
                record_number,
            )
        )

        return self.fetch_one()
    
    def get_all_evidence(
        self,
        case_id
    ):

        self._query(
            """
            SELECT *

            FROM evidence

            WHERE case_id = ?

            ORDER BY record_number
            """,
            (case_id,)
        )

        return self.fetch_all()
    
    def get_evidence_tree(
        self,
        case_id
    ):

        self._query(
            """
            SELECT *

            FROM evidence

            WHERE case_id = ?

            ORDER BY full_path
            """,
            (case_id,)
        )

        return self.fetch_all()
    
    def get_container_artifacts(
        self,
        case_id
    ):

        self._query(
            """
            SELECT *

            FROM container_artifacts

            WHERE case_id = ?

            ORDER BY parent_record, path
            """,
            (case_id,)
        )

        return self.fetch_all()

    def get_timeline_events(
        self,
        case_id
    ):

        self._query(

            """
            SELECT *

            FROM timeline_events

            WHERE case_id = ?

            ORDER BY timestamp
            """,

            (case_id,)

        )

        return self.fetch_all()

    def get_timeline_events_for_record(
        self,
        case_id,
        record_number
    ):

        self._query(

            """
            SELECT *

            FROM timeline_events

            WHERE case_id = ?
            AND record_number = ?

            ORDER BY timestamp
            """,

            (
                case_id,
                record_number,
            )

        )

        return self.fetch_all()


    def get_container_artifact(
    self,
    parent_record,
    path
    ):

        self._query(
            """
            SELECT *

            FROM container_artifacts

            WHERE parent_record = ?
            AND path = ?
            """,
            (
                parent_record,
                path,
            )
        )

        return self.fetch_one()

    
    def replace_unallocated_regions(
        self, case_id, image_path, regions
    ):
        import os

        normalized_path = os.path.normcase(
            os.path.abspath(image_path)
        )

        try:
            self._execute(
                """
                DELETE FROM unallocated_regions
                WHERE case_id = ? AND image_path = ?
                """,
                (case_id, normalized_path),
            )

            parameters = [
                (
                    case_id,
                    normalized_path,
                    region.start_cluster,
                    region.end_cluster,
                    region.cluster_count,
                    region.start_offset,
                    region.end_offset,
                    region.byte_count,
                    region.state,
                )
                for region in regions
            ]

            if parameters:
                self._execute_many(
                    """
                    INSERT INTO unallocated_regions (
                        case_id,
                        image_path,
                        start_cluster,
                        end_cluster,
                        cluster_count,
                        start_offset,
                        end_offset,
                        byte_count,
                        state
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    parameters,
                )

            self.save()

        except Exception:
            self.database.connection.rollback()
            raise


    def get_unallocated_regions(self, case_id, image_path):
        import os

        normalized_path = os.path.normcase(
            os.path.abspath(image_path)
        )

        self._query(
            """
            SELECT
                region_id,
                case_id,
                image_path,
                start_cluster,
                end_cluster,
                cluster_count,
                start_offset,
                end_offset,
                byte_count,
                state
            FROM unallocated_regions
            WHERE case_id = ? AND image_path = ?
            ORDER BY start_offset
            """,
            (case_id, normalized_path),
        )

        return self.fetch_all()
