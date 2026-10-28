from types import SimpleNamespace


class ContainerMapper:

    @staticmethod
    def to_object(row):

        return SimpleNamespace(

            artifact_id=row[0],

            case_id=row[1],

            parent_record=row[2],

            path=row[3],

            name=row[4],

            directory=bool(row[5]),

            size=row[6],

            mime_type=row[7],

        )

    @classmethod
    def to_object_list(cls, rows):

        return [

            cls.to_object(row)

            for row in rows

        ]