class DatabaseSchema:

    def __init__(self, database):

        self.database = database
        self.cursor = database.cursor

    def create_schema(self):

        self.create_cases_table()
        self.migrate_cases_table()
        self.create_evidence_table()
        self.create_container_artifacts_table()
        self.create_timeline_events_table()
        self.create_recovered_artifacts_table()
        self.create_unallocated_regions_table()
        self.create_metafiles_table()
        self.create_deleted_files_table()

        self.database.commit()

    def create_deleted_files_table(self):

        from database.deleted_file_repository import CREATE_DELETED_FILES_TABLE

        self.cursor.execute(CREATE_DELETED_FILES_TABLE)

    def create_metafiles_table(self):

        from database.metafile_repository import CREATE_METAFILES_TABLE

        self.cursor.execute(CREATE_METAFILES_TABLE)

    def create_cases_table(self):

        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS cases (
                case_id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_name TEXT NOT NULL,
                image_path TEXT,
                created_at TEXT,
                investigator TEXT,
                description TEXT,
                status TEXT NOT NULL DEFAULT 'complete',
                engine_version TEXT,
                completed_at TEXT
            )
            """
        )

    # Columns added after the first release, appended at the end so that
    # positional reads of older columns (e.g. image_path) keep working.
    CASE_COLUMNS_ADDED = {
        "status": "TEXT NOT NULL DEFAULT 'complete'",
        "engine_version": "TEXT",
        "completed_at": "TEXT",
    }

    def migrate_cases_table(self):

        columns = {row[1] for row in self.cursor.execute("PRAGMA table_info(cases)")}
        for name, definition in self.CASE_COLUMNS_ADDED.items():
            if name not in columns:
                self.cursor.execute(f"ALTER TABLE cases ADD COLUMN {name} {definition}")
    
    def create_evidence_table(self):

        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS evidence (
                evidence_id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                record_number INTEGER NOT NULL,
                parent_record INTEGER,
                filename TEXT,
                full_path TEXT,
                file_size INTEGER,
                allocated_size INTEGER,
                slack_space INTEGER,
                slack_entropy REAL,
                fragment_count INTEGER,
                fragmented INTEGER,
                fragment_ratio REAL,
                deleted INTEGER,
                directory INTEGER,
                risk_score INTEGER,
                record_type TEXT,
                FOREIGN KEY (case_id) REFERENCES cases(case_id)
            )
            """
        )
    
    def create_container_artifacts_table(self):

        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS container_artifacts (

                artifact_id INTEGER PRIMARY KEY AUTOINCREMENT,

                case_id INTEGER NOT NULL,

                parent_record INTEGER NOT NULL,

                path TEXT NOT NULL,

                name TEXT NOT NULL,

                directory INTEGER NOT NULL,

                size INTEGER,

                mime_type TEXT,

                FOREIGN KEY(case_id)
                    REFERENCES cases(case_id)

            )
            """
        )

    def create_timeline_events_table(self):

        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS timeline_events (

                event_id INTEGER PRIMARY KEY AUTOINCREMENT,

                case_id INTEGER NOT NULL,

                record_number INTEGER,

                filename TEXT,

                full_path TEXT,

                timestamp TEXT NOT NULL,

                event_type TEXT NOT NULL,

                deleted INTEGER NOT NULL,

                directory INTEGER NOT NULL,

                source TEXT NOT NULL,

                artifact_type TEXT NOT NULL,

                description TEXT,

                FOREIGN KEY(case_id)
                    REFERENCES cases(case_id)

            )
            """
        )

    def create_recovered_artifacts_table(self):

        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS recovered_artifacts (

                artifact_id INTEGER PRIMARY KEY AUTOINCREMENT,

                case_id INTEGER NOT NULL,

                signature TEXT NOT NULL,
                extension TEXT NOT NULL,
                size INTEGER NOT NULL,
                sha256 TEXT NOT NULL,
                confidence REAL NOT NULL,

                source_image TEXT NOT NULL,
                source_type TEXT NOT NULL,

                region_start_cluster INTEGER NOT NULL,
                region_end_cluster INTEGER NOT NULL,
                region_start_offset INTEGER NOT NULL,

                source_offset INTEGER NOT NULL,
                relative_offset INTEGER NOT NULL,

                start_cluster INTEGER NOT NULL,
                end_cluster INTEGER NOT NULL,

                validation_reason TEXT NOT NULL,

                -- JSON [[offset, length], ...] for reassembled files.
                fragments TEXT,

                FOREIGN KEY(case_id)
                    REFERENCES cases(case_id)

            )
            """
        )

    
    def create_unallocated_regions_table(self):
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS unallocated_regions (
                region_id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                image_path TEXT NOT NULL,

                start_cluster INTEGER NOT NULL,
                end_cluster INTEGER NOT NULL,
                cluster_count INTEGER NOT NULL,

                start_offset INTEGER NOT NULL,
                end_offset INTEGER NOT NULL,
                byte_count INTEGER NOT NULL,

                state TEXT NOT NULL DEFAULT 'UNALLOCATED',

                FOREIGN KEY (case_id)
                    REFERENCES cases(case_id),

                UNIQUE (
                    case_id,
                    image_path,
                    start_cluster,
                    end_cluster,
                    start_offset,
                    end_offset
                )
            )
            """
        )
