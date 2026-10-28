import io

from database.case import Case
from database.case_database import Database
from database.repository import Repository
from database.schema import DatabaseSchema
from engine.allocation.allocation_models import UnallocatedRegion
from engine.allocation.unallocated_recovery_application import UnallocatedRecoveryApplication
from support.jpeg_samples import TINY_JPEG


class SyntheticParser:
    cluster_size = 4096
    allocation_ranges = [
        {"start_cluster": 0, "end_cluster": 1, "cluster_count": 2, "state": "unallocated"},
    ]

    def get_unallocated_regions(self):
        return [UnallocatedRegion(
            start_cluster=0,
            end_cluster=1,
            cluster_count=2,
            start_offset=0,
            end_offset=8192,
            byte_count=8192,
        )]


def test_application_scans_validates_carves_and_persists_jpeg(tmp_path):
    image_data = bytearray(b"\x00" * 8192)
    # Must be a structurally valid JPEG: the validator walks every segment.
    jpeg = TINY_JPEG
    image_data[100:100 + len(jpeg)] = jpeg
    image = io.BytesIO(bytes(image_data))

    database = Database()
    database.create_case("Unallocated Application Test", directory=str(tmp_path))
    try:
        DatabaseSchema(database).create_schema()
        case = Case()
        case.case_name = "Unallocated Application Test"
        case.image_path = "synthetic.img"
        case_id = Repository(database).insert_case(case)

        result = UnallocatedRecoveryApplication(
            chunk_size=1024,
            window_size=256,
        ).run(
            image=image,
            parser=SyntheticParser(),
            database=database,
            case_id=case_id,
            source_image="synthetic.img",
        )

        assert result["success"] is True
        assert result["candidates_detected"] == 1
        assert result["candidates_validated"] == 1
        assert result["recovered_count"] == 1
        assert result["artifacts"][0]["signature"] == "JPEG"
        assert result["artifacts"][0]["size"] == len(jpeg)

        # Re-running a scan must not duplicate persisted evidence records.
        repeated = UnallocatedRecoveryApplication(
            chunk_size=1024,
            window_size=256,
        ).run(
            image=image,
            parser=SyntheticParser(),
            database=database,
            case_id=case_id,
            source_image="synthetic.img",
        )
        assert repeated["recovered_count"] == 0
        assert repeated["recovery_status_counts"]["ALREADY_PERSISTED"] == 1
    finally:
        database.close()
