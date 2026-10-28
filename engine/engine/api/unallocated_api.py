"""Application-facing API for NTFS unallocated (free) space.

Regions are computed once, during ``analyze``, and stored in the case
database. Listing regions and reading raw bytes therefore never re-parse
the MFT; the hex viewer can page through free space cheaply.
"""
from contextlib import contextmanager

from database.case_database import Database
from database.repository import Repository
from database.schema import DatabaseSchema
from engine.allocation.allocation_models import UnallocatedRegion
from engine.allocation.unallocated_recovery_application import (
    UnallocatedRecoveryApplication,
)
from engine.api.case_access import validate_case_image
from engine.errors import NotFoundError, UsageError
from engine.volume.opener import open_ntfs_volume


class UnallocatedAPI:

    # Keep individual raw reads small for predictable memory use.
    MAX_READ_SIZE = 64 * 1024

    # -----------------------------------------------------------------
    # Commands
    # -----------------------------------------------------------------

    def list_regions(self, image_path, database_path, case_id):
        """List free-space regions for a case without carving anything."""
        with self._case(database_path) as repository:
            validate_case_image(repository, case_id, image_path)
            regions, source = self._regions(repository, case_id, image_path)

        return {
            "success": True,
            "case_id": case_id,
            "region_count": len(regions),
            "source": source,
            "regions": [
                {
                    "index": index,
                    "start_cluster": region.start_cluster,
                    "end_cluster": region.end_cluster,
                    "cluster_count": region.cluster_count,
                    "start_offset": region.start_offset,
                    "end_offset": region.end_offset,
                    "byte_count": region.byte_count,
                    "state": region.state,
                }
                for index, region in enumerate(regions)
            ],
        }

    def read_region(
        self, image_path, database_path, case_id, region_index, offset, size
    ):
        """Read a bounded slice of raw bytes from one free-space region."""
        if region_index < 0:
            raise UsageError("region_index cannot be negative")
        if offset < 0:
            raise UsageError("offset cannot be negative")
        if size <= 0 or size > self.MAX_READ_SIZE:
            raise UsageError(
                f"size must be between 1 and {self.MAX_READ_SIZE} bytes"
            )

        with self._case(database_path) as repository:
            validate_case_image(repository, case_id, image_path)
            regions, _ = self._regions(repository, case_id, image_path)

        if region_index >= len(regions):
            raise NotFoundError(
                f"Unallocated region {region_index} does not exist "
                f"(the case has {len(regions)} regions)"
            )

        region = regions[region_index]

        if offset + size > region.byte_count:
            raise UsageError(
                "Requested byte range exceeds the selected region"
            )

        absolute_offset = region.start_offset + offset

        with open(image_path, "rb") as image:
            image.seek(absolute_offset)
            data = image.read(size)

        if len(data) != size:
            raise IOError("Short read while reading the evidence image")

        return {
            "success": True,
            "case_id": case_id,
            "region_index": region_index,
            "region_offset": offset,
            "absolute_offset": absolute_offset,
            "size": len(data),
            "encoding": "hex",
            "data": data.hex(),
        }

    def recover(self, image_path, database_path, case_id):
        """Scan free space for known file signatures and store the results.

        This can take a long time on large images.
        """
        database = Database()
        try:
            database.open_case(database_path)
            repository = Repository(database)
            validate_case_image(repository, case_id, image_path)

            with open(image_path, "rb") as image:
                parser = open_ntfs_volume(image, repository, case_id)
                # Only $Bitmap is needed; enumerating the whole MFT is not.
                parser.load_allocation()

                return UnallocatedRecoveryApplication().run(
                    image=image,
                    parser=parser,
                    database=database,
                    case_id=case_id,
                    source_image=image_path,
                )
        finally:
            database.close()

    # -----------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------

    @contextmanager
    def _case(self, database_path):
        database = Database()
        try:
            database.open_case(database_path)
            # Case databases created before free-space support lack the
            # table; creating it is idempotent.
            DatabaseSchema(database).create_unallocated_regions_table()
            database.commit()
            yield Repository(database)
        finally:
            database.close()

    def _regions(self, repository, case_id, image_path):
        """Return (regions, source); source is "database" or "image"."""
        rows = repository.get_unallocated_regions(case_id, image_path)

        if rows:
            return [self._region_from_row(row) for row in rows], "database"

        # Not stored yet (case analyzed by an older engine version):
        # compute from $Bitmap once and store for next time.
        with open(image_path, "rb") as image:
            parser = open_ntfs_volume(image)
            parser.load_allocation()
            regions = parser.get_unallocated_regions()

        repository.replace_unallocated_regions(
            case_id=case_id,
            image_path=image_path,
            regions=regions,
        )

        return regions, "image"

    @staticmethod
    def _region_from_row(row):
        # region_id, case_id, image_path, start_cluster, end_cluster,
        # cluster_count, start_offset, end_offset, byte_count, state
        return UnallocatedRegion(
            start_cluster=row[3],
            end_cluster=row[4],
            cluster_count=row[5],
            start_offset=row[6],
            end_offset=row[7],
            byte_count=row[8],
            state=row[9],
        )
