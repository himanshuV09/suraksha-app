class EvidenceMapper:

    COLUMNS = [

        "evidence_id",

        "case_id",

        "record_number",

        "parent_record",

        "filename",

        "full_path",

        "file_size",

        "allocated_size",

        "slack_space",

        "slack_entropy",

        "fragment_count",

        "fragmented",

        "fragment_ratio",

        "deleted",

        "directory",

        "risk_score",

        "record_type",

    ]

    @classmethod
    def to_dict(cls, row):

        return dict(

            zip(

                cls.COLUMNS,

                row

            )

        )

    @classmethod
    def to_dict_list(cls, rows):

        return [

            cls.to_dict(row)

            for row in rows

        ]