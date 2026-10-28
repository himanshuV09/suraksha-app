"""List the cases stored in the cases directory (for the Cases screen)."""
import sqlite3
from pathlib import Path

from engine.paths import DEFAULT_CASES_DIR


def _read_only(path):
    # mode=ro: listing cases must never modify evidence databases.
    return sqlite3.connect(f"file:{Path(path).as_posix()}?mode=ro", uri=True)


class CaseAPI:

    def list_cases(self, cases_dir=None):
        directory = Path(cases_dir) if cases_dir else DEFAULT_CASES_DIR
        cases, unreadable = [], []

        for database in sorted(directory.glob("*.db")) if directory.is_dir() else []:
            try:
                connection = _read_only(database)
            except sqlite3.Error as error:
                unreadable.append({"database_path": str(database), "error": str(error)})
                continue
            try:
                cases += self._cases_in(connection, database)
            except sqlite3.Error as error:
                unreadable.append({"database_path": str(database), "error": str(error)})
            finally:
                connection.close()

        cases.sort(key=lambda case: case["created_at"] or "", reverse=True)
        return {
            "success": True,
            "cases_dir": str(directory.resolve()),
            "count": len(cases),
            "cases": cases,
            "unreadable": unreadable,
        }

    @staticmethod
    def _cases_in(connection, database):
        tables = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )}
        if "cases" not in tables:
            return []
        columns = {row[1] for row in connection.execute("PRAGMA table_info(cases)")}

        def column(name):
            return name if name in columns else f"NULL AS {name}"

        evidence = (
            "(SELECT COUNT(*) FROM evidence e WHERE e.case_id = c.case_id)"
            if "evidence" in tables else "0"
        )
        rows = connection.execute(f"""
            SELECT case_id, case_name, image_path, created_at, investigator,
                   description, {column('status')}, {column('engine_version')},
                   {column('completed_at')}, {evidence} AS evidence_count
            FROM cases c
        """).fetchall()

        keys = ("case_id", "case_name", "image_path", "created_at", "investigator",
                "description", "status", "engine_version", "completed_at",
                "evidence_count")
        result = []
        for row in rows:
            case = dict(zip(keys, row))
            # Cases from before status tracking finished if they have data.
            if case["status"] is None:
                case["status"] = "complete" if case["evidence_count"] else "unknown"
            case["database_path"] = str(Path(database).resolve())
            case["image_available"] = bool(case["image_path"]) and Path(case["image_path"]).is_file()
            result.append(case)
        return result
