"""Persistence for deleted-file recoverability assessments."""
import json

CREATE_DELETED_FILES_TABLE = """
    CREATE TABLE IF NOT EXISTS deleted_files (
        deleted_file_id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id INTEGER NOT NULL,
        record_number INTEGER NOT NULL,
        sequence_number INTEGER,
        filename TEXT NOT NULL,
        full_path TEXT NOT NULL,
        file_size INTEGER NOT NULL,
        resident INTEGER NOT NULL,
        status TEXT NOT NULL,
        total_clusters INTEGER NOT NULL,
        free_clusters INTEGER NOT NULL,
        reused_clusters INTEGER NOT NULL,
        recoverable_bytes INTEGER NOT NULL,
        recoverable_percent REAL NOT NULL,
        overwritten_by TEXT NOT NULL DEFAULT '[]',
        unreliable_ranges TEXT NOT NULL DEFAULT '[]',
        content_check TEXT NOT NULL DEFAULT 'unknown',
        created TEXT,
        modified TEXT,
        accessed TEXT,
        mft_modified TEXT,
        FOREIGN KEY (case_id) REFERENCES cases(case_id),
        UNIQUE (case_id, record_number)
    )
"""

_COLUMNS = (
    "record_number", "sequence_number", "filename", "full_path", "file_size",
    "resident", "status", "total_clusters", "free_clusters", "reused_clusters",
    "recoverable_bytes", "recoverable_percent", "overwritten_by", "unreliable_ranges",
    "content_check",
    "created", "modified", "accessed", "mft_modified",
)


_ADDED_COLUMNS = {
    "unreliable_ranges": "TEXT NOT NULL DEFAULT '[]'",
    "content_check": "TEXT NOT NULL DEFAULT 'unknown'",
}


def _iso(value):
    return value.isoformat() if value is not None else None


class DeletedFileRepository:

    def __init__(self, database):
        if database is None or database.cursor is None:
            raise ValueError("database must be open")
        self.database = database
        self.cursor = database.cursor

    def ensure_schema(self):
        self.cursor.execute(CREATE_DELETED_FILES_TABLE)
        # Add columns introduced after a database was created.
        columns = {row[1] for row in self.cursor.execute("PRAGMA table_info(deleted_files)")}
        for name, definition in _ADDED_COLUMNS.items():
            if name not in columns:
                self.cursor.execute(f"ALTER TABLE deleted_files ADD COLUMN {name} {definition}")
        self.database.commit()

    def replace(self, case_id, assessments):
        """Store a case's assessments, replacing any earlier ones."""
        self.ensure_schema()
        rows = [
            (
                case_id,
                item.record_number,
                item.sequence_number,
                item.filename,
                item.full_path,
                item.file_size,
                int(item.resident),
                item.status,
                item.total_clusters,
                item.free_clusters,
                item.reused_clusters,
                item.recoverable_bytes,
                item.recoverable_percent,
                json.dumps(item.overwritten_by),
                json.dumps(item.unreliable_ranges),
                item.content_check,
                _iso(item.created),
                _iso(item.modified),
                _iso(item.accessed),
                _iso(item.mft_modified),
            )
            for item in assessments
        ]
        try:
            self.cursor.execute("DELETE FROM deleted_files WHERE case_id = ?", (case_id,))
            self.cursor.executemany(
                f"INSERT INTO deleted_files (case_id, {', '.join(_COLUMNS)}) "
                f"VALUES ({', '.join('?' * (len(_COLUMNS) + 1))})",
                rows,
            )
            self.database.commit()
        except Exception:
            self.database.connection.rollback()
            raise

    def list_by_case(self, case_id, statuses=None, record_numbers=None):
        """Stored assessments as dicts, optionally filtered."""
        self.ensure_schema()
        query = f"SELECT {', '.join(_COLUMNS)} FROM deleted_files WHERE case_id = ?"
        parameters = [case_id]
        if statuses:
            query += f" AND status IN ({', '.join('?' * len(statuses))})"
            parameters += list(statuses)
        if record_numbers:
            query += f" AND record_number IN ({', '.join('?' * len(record_numbers))})"
            parameters += list(record_numbers)
        query += " ORDER BY full_path COLLATE NOCASE, record_number"

        self.cursor.execute(query, parameters)
        result = []
        for row in self.cursor.fetchall():
            item = dict(zip(_COLUMNS, row))
            item["resident"] = bool(item["resident"])
            item["overwritten_by"] = json.loads(item["overwritten_by"])
            item["unreliable_ranges"] = json.loads(item["unreliable_ranges"])
            result.append(item)
        return result
