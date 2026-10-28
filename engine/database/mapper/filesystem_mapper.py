from types import SimpleNamespace


class FilesystemMapper:

    @staticmethod
    def to_object(row):

        return SimpleNamespace(

            evidence_id=row[0],

            case_id=row[1],

            record_number=row[2],

            parent_record=row[3],

            filename=row[4],

            full_path=row[5],

            file_size=row[6],

            allocated_size=row[7],

            slack_space=row[8],

            slack_entropy=row[9],

            fragment_count=row[10],

            fragmented=bool(row[11]),

            fragment_ratio=row[12],

            deleted=bool(row[13]),

            directory=bool(row[14]),

            risk_score=row[15],

            record_type=row[16],

            children=[]

        )

    @classmethod
    def to_object_list(

        cls,

        rows

    ):

        return [

            cls.to_object(row)

            for row in rows

        ]
    
        
    @staticmethod
    def to_dictionary(evidence):

        return {

            "evidence_id": evidence.evidence_id,

            "case_id": evidence.case_id,

            "record_number": evidence.record_number,

            "parent_record": evidence.parent_record,

            "filename": evidence.filename,

            "full_path": evidence.full_path,

            "file_size": evidence.file_size,

            "allocated_size": evidence.allocated_size,

            "slack_space": evidence.slack_space,

            "slack_entropy": evidence.slack_entropy,

            "fragment_count": evidence.fragment_count,

            "fragmented": evidence.fragmented,

            "fragment_ratio": evidence.fragment_ratio,

            "deleted": evidence.deleted,

            "directory": evidence.directory,

            "risk_score": evidence.risk_score,

            "record_type": evidence.record_type,

        }