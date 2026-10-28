import json

from engine.allocation.recovered_artifact_record import (
    RecoveredArtifactRecord,
)


from engine.allocation.recovered_artifact_metadata import (
    RecoveredArtifactMetadata,
)


class RecoveredArtifactRepository:
    """
    Persistence boundary for recovered forensic artifacts.

    This repository stores already-validated
    RecoveredArtifactRecord objects in the case database.

    It does not perform:

        - carving
        - validation
        - hashing
        - allocation analysis
        - provenance construction
        - filesystem recovery
    """

    def __init__(self, database):
        if database is None:
            raise ValueError(
                "database cannot be None"
            )

        if database.cursor is None:
            raise ValueError(
                "database must be open"
            )

        self.database = database
        self.cursor = database.cursor
        self._ensure_fragments_column()

    def _ensure_fragments_column(self):
        """Add the fragments column to databases created before it existed."""
        table = self.cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='recovered_artifacts'"
        ).fetchone()
        if table is None:
            return
        columns = {row[1] for row in self.cursor.execute("PRAGMA table_info(recovered_artifacts)")}
        if "fragments" not in columns:
            self.cursor.execute("ALTER TABLE recovered_artifacts ADD COLUMN fragments TEXT")
            self.database.commit()

    def create_fragmented(self, case_id, *, signature, extension, size, sha256,
                          confidence, source_image, region, fragments,
                          cluster_size, volume_offset, validation_reason):
        """Store a file reassembled from several free-space pieces.

        ``region`` is the free region holding the first piece; cluster and
        offset columns describe that first piece, ``fragments`` all pieces.
        """
        first_offset, first_length = fragments[0]
        start_cluster = (first_offset - volume_offset) // cluster_size
        end_cluster = (first_offset + first_length - 1 - volume_offset) // cluster_size
        self.cursor.execute(
            """
            INSERT INTO recovered_artifacts (
                case_id, signature, extension, size, sha256, confidence,
                source_image, source_type,
                region_start_cluster, region_end_cluster, region_start_offset,
                source_offset, relative_offset, start_cluster, end_cluster,
                validation_reason, fragments
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                case_id, signature, extension, size, sha256, confidence,
                source_image, "UNALLOCATED_FRAGMENTED",
                region.start_cluster, region.end_cluster, region.start_offset,
                first_offset, first_offset - region.start_offset,
                start_cluster, end_cluster,
                validation_reason, json.dumps([list(piece) for piece in fragments]),
            ),
        )
        self.database.commit()
        return self.cursor.lastrowid

    def create(
        self,
        case_id,
        record,
    ):
        if not isinstance(case_id, int):
            raise TypeError(
                "case_id must be an integer"
            )

        if case_id <= 0:
            raise ValueError(
                "case_id must be greater than zero"
            )

        if not isinstance(
            record,
            RecoveredArtifactRecord,
        ):
            raise TypeError(
                "record must be a RecoveredArtifactRecord"
            )

        provenance = record.provenance
        artifact = record.artifact

        self.cursor.execute(
            """
            INSERT INTO recovered_artifacts (
                case_id,
                signature,
                extension,
                size,
                sha256,
                confidence,
                source_image,
                source_type,
                region_start_cluster,
                region_end_cluster,
                region_start_offset,
                source_offset,
                relative_offset,
                start_cluster,
                end_cluster,
                validation_reason
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                case_id,
                record.signature,
                record.extension,
                record.size,
                record.sha256,
                record.confidence,
                provenance.source_image,
                provenance.source_type,
                provenance.region_start_cluster,
                provenance.region_end_cluster,
                provenance.region_start_offset,
                provenance.source_offset,
                provenance.relative_offset,
                provenance.start_cluster,
                provenance.end_cluster,
                artifact.candidate.validation_reason,
            ),
        )

        self.database.commit()

        return self.cursor.lastrowid

    def get(
        self,
        artifact_id,
    ):
        if not isinstance(artifact_id, int):
            raise TypeError(
                "artifact_id must be an integer"
            )

        if artifact_id <= 0:
            raise ValueError(
                "artifact_id must be greater than zero"
            )

        self.cursor.execute(
            """
            SELECT
                artifact_id,
                signature,
                extension,
                size,
                sha256,
                confidence,
                source_image,
                source_type,
                region_start_cluster,
                region_end_cluster,
                region_start_offset,
                source_offset,
                relative_offset,
                start_cluster,
                end_cluster,
                validation_reason
            FROM recovered_artifacts
            WHERE artifact_id = ?
            """,
            (artifact_id,),
        )

        row = self.cursor.fetchone()

        if row is None:
            raise KeyError(
                f"Recovered artifact not found: {artifact_id}"
            )

        (   
            artifact_id,
            signature,
            extension,
            size,
            sha256,
            confidence,
            source_image,
            source_type,
            region_start_cluster,
            region_end_cluster,
            region_start_offset,
            source_offset,
            relative_offset,
            start_cluster,
            end_cluster,
            validation_reason,
        ) = row

        return RecoveredArtifactMetadata(
            artifact_id=artifact_id,
            signature=signature,
            extension=extension,
            size=size,
            sha256=sha256,
            confidence=confidence,
            source_image=source_image,
            source_type=source_type,
            region_start_cluster=region_start_cluster,
            region_end_cluster=region_end_cluster,
            region_start_offset=region_start_offset,
            source_offset=source_offset,
            relative_offset=relative_offset,
            start_cluster=start_cluster,
            end_cluster=end_cluster,
            validation_reason=validation_reason,
        )

    def list_by_case(
        self,
        case_id,
    ):
        if not isinstance(case_id, int):
            raise TypeError(
                "case_id must be an integer"
            )

        if case_id <= 0:
            raise ValueError(
                "case_id must be greater than zero"
            )

        self.cursor.execute(
            """
            SELECT
                artifact_id,
                signature,
                extension,
                size,
                sha256,
                confidence,
                source_image,
                source_type,
                region_start_cluster,
                region_end_cluster,
                region_start_offset,
                source_offset,
                relative_offset,
                start_cluster,
                end_cluster,
                validation_reason,
                fragments
            FROM recovered_artifacts
            WHERE case_id = ?
            ORDER BY artifact_id ASC
            """,
            (case_id,),
        )

        rows = self.cursor.fetchall()

        return [
            RecoveredArtifactMetadata(
                artifact_id=row[0],
                signature=row[1],
                extension=row[2],
                size=row[3],
                sha256=row[4],
                confidence=row[5],
                source_image=row[6],
                source_type=row[7],
                region_start_cluster=row[8],
                region_end_cluster=row[9],
                region_start_offset=row[10],
                source_offset=row[11],
                relative_offset=row[12],
                start_cluster=row[13],
                end_cluster=row[14],
                validation_reason=row[15],
                fragments=json.loads(row[16]) if row[16] else None,
            )
            for row in rows
        ]

        