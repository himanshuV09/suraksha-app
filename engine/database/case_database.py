import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from engine.paths import DEFAULT_CASES_DIR, safe_filename

class Database:

    def __init__(self):

        self.connection = None
        self.cursor = None

        self.case_name = None
        self.database_path = None

        self.created_time = None

    def create_case(
            self,
            case_name,
            directory=None
    ):
        directory = Path(directory) if directory else DEFAULT_CASES_DIR
        os.makedirs(directory, exist_ok=True)

        self.case_name = case_name

        # Always absolute, so callers can hand the path to another process.
        self.database_path = str(
            (directory / f"{safe_filename(case_name)}.db").resolve()
        )

        self.connection = sqlite3.connect(self.database_path)

        self.cursor = self.connection.cursor()

        self.created_time = datetime.now()

        print(
            f"Case created: {self.database_path}", file=sys.stderr
        )

    def open_case(
            self,
            database_path
    ):
        database_path = Path(database_path)

        # Relative paths: try the working directory first, then the
        # engine's cases directory (older clients sent "cases/<name>.db").
        if not database_path.is_absolute() and not database_path.exists():
            for candidate in (
                DEFAULT_CASES_DIR / database_path,
                DEFAULT_CASES_DIR.parent / database_path,
            ):
                if candidate.exists():
                    database_path = candidate
                    break

        database_path = database_path.resolve()

        if not database_path.is_file():
            raise FileNotFoundError(
                f"Case database not found: {database_path}"
            )

        self.database_path = str(database_path)
        self.case_name = database_path.stem

        self.connection = sqlite3.connect(self.database_path)
        self.cursor = self.connection.cursor()

        print(f"Case opened: {self.case_name}", file=sys.stderr)
        
    def commit(self):
        if self.connection:
            self.connection.commit()

    def close(self):

        if self.connection:
            
            self.connection.close()

            self.connection = None
            self.cursor = None

            print("Case closed.", file=sys.stderr)
        
    def is_open(self):
        
        return self.connection is not None
