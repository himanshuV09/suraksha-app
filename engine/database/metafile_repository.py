"""Persistence for the per-case NTFS metafile summary."""
import json

CREATE_METAFILES_TABLE = """
    CREATE TABLE IF NOT EXISTS metafiles (
        metafile_id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id INTEGER NOT NULL,
        record_number INTEGER NOT NULL,
        name TEXT NOT NULL,
        status TEXT NOT NULL,
        in_use INTEGER,
        size INTEGER NOT NULL DEFAULT 0,
        allocated_size INTEGER NOT NULL DEFAULT 0,
        resident INTEGER,
        fragments INTEGER NOT NULL DEFAULT 0,
        streams TEXT NOT NULL DEFAULT '[]',
        created TEXT,
        modified TEXT,
        details TEXT NOT NULL DEFAULT '{}',
        error TEXT,
        FOREIGN KEY (case_id) REFERENCES cases(case_id),
        UNIQUE (case_id, record_number, name)
    )
"""

_COLUMNS = (
    "record_number", "name", "status", "in_use", "size", "allocated_size",
    "resident", "fragments", "streams", "created", "modified", "details", "error",
)


def _optional_bool(value):
    return None if value is None else int(bool(value))


def _iso(value):
    return value.isoformat() if value is not None else None


class MetafileRepository:

    def __init__(self, database):
        if database is None or database.cursor is None:
            raise ValueError("database must be open")
        self.database = database
        self.cursor = database.cursor

    def ensure_schema(self):
        self.cursor.execute(CREATE_METAFILES_TABLE)
        self.database.commit()

    def replace(self, case_id, metafiles):
        """Store a case's metafile summary, replacing any earlier one."""
        self.ensure_schema()
        rows = [
            (
                case_id,
                item.record_number,
                item.name,
                item.status,
                _optional_bool(item.in_use),
                item.size,
                item.allocated_size,
                _optional_bool(item.resident),
                item.fragments,
                json.dumps(item.streams, default=str),
                _iso(item.created),
                _iso(item.modified),
                json.dumps(item.details, default=str),
                item.error,
            )
            for item in metafiles
        ]
        try:
            self.cursor.execute("DELETE FROM metafiles WHERE case_id = ?", (case_id,))
            self.cursor.executemany(
                f"INSERT INTO metafiles (case_id, {', '.join(_COLUMNS)}) "
                f"VALUES ({', '.join('?' * (len(_COLUMNS) + 1))})",
                rows,
            )
            self.database.commit()
        except Exception:
            self.database.connection.rollback()
            raise

    def list_by_case(self, case_id):
        """Return the stored summary as dicts, ordered by record number."""
        self.ensure_schema()
        self.cursor.execute(
            f"SELECT {', '.join(_COLUMNS)} FROM metafiles "
            "WHERE case_id = ? ORDER BY record_number, name",
            (case_id,),
        )
        result = []
        for row in self.cursor.fetchall():
            item = dict(zip(_COLUMNS, row))
            item["streams"] = json.loads(item["streams"])
            item["details"] = json.loads(item["details"])
            for flag in ("in_use", "resident"):
                if item[flag] is not None:
                    item[flag] = bool(item[flag])
            result.append(item)
        return result
