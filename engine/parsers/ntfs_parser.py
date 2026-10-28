import sys
import math

from ntfs import parse_boot_sector

from enumerator import (
    read_mft_record,
    is_valid_mft_record,
    classify_mft_record,
)

from mft import parse_mft_header

from attributes import parse_attributes

from non_resident import (
    parse_non_resident_attribute,
    parse_data_runs,
)

from engine.allocation.bitmap import load_bitmap, decode_bitmap

from engine.allocation.unallocated_reader import UnallocatedReader

from engine.allocation.unallocated_scanner import UnallocatedScanner

from engine.allocation.allocation_models import UnallocatedRegion

from engine.allocation.unallocated_region_service import (
    UnallocatedRegionService
)

from fixup import apply_fixup

from engine import progress

from engine.volume.geometry import VolumeGeometry

from engine.volume.mft_locator import MftRecordLocator

from .record_processor import RecordProcessor


# MFT record numbers of NTFS system files used by the parser.
MFT_RECORD = 0
BITMAP_RECORD = 6

# How many individual record errors to keep for the analysis report.
MAX_RECORD_ERRORS = 100


class NTFSParser:

    def __init__(
        self,
        image,
        repository,
        case_id,
        volume_offset=0
    ):

        self.image = image

        self.repository = repository

        self.case_id = case_id

        self.volume_offset = volume_offset

        self.total_clusters = None

        self.cluster_size = None

        self.total_clusters = None

        self.mft_offset = None

        self.record_size = None

        self.ntfs_info = None

        # Actual $MFT geometry
        self.mft_size = None

        self.mft_allocated_size = None

        self.mft_record_count = None

        self.mft_data_runs = []

        # Set once $MFT's data runs are known; see determine_mft_geometry().
        self.mft_locator = None

        self.allocation_ranges = []

        # Problems that did not stop parsing, for the analysis report.
        self.warnings = []

        # Records that could not be parsed: [{"record_number", "error"}].
        # Only the first MAX_RECORD_ERRORS are kept; the total is counted.
        self.record_errors = []
        self.record_error_count = 0

        self.mft_slots = 0

        self.allocated_records = 0

        self.deleted_records = 0

        self.unused_records = 0

        self.corrupt_records = 0

        self.record_processor = RecordProcessor(
            repository,
            case_id
        )

    # ---------------------------------------------------------
    # NTFS BOOT SECTOR
    # ---------------------------------------------------------

    def parse_boot_sector(self):

        # Always read from the beginning of the image.
        if not isinstance(self.volume_offset, int) or self.volume_offset < 0:
            raise ValueError("volume_offset must be a non-negative integer")

        self.image.seek(self.volume_offset)

        boot_sector = self.image.read(512)

        if len(boot_sector) != 512:
            raise Exception(
                "Unable to read complete NTFS boot sector"
            )

        oem_id = boot_sector[3:11]

        print(
            "OEM ID:",
            oem_id,
            file=sys.stderr
        )

        if oem_id != b"NTFS    ":

            raise Exception(
                "NTFS file system not detected"
            )

        print(
            "\nNTFS filesystem detected",
            file=sys.stderr
        )

        ntfs_info = parse_boot_sector(
            boot_sector
        )

        print(
            "\nNTFS Boot Sector Information\n",
            file=sys.stderr
        )

        for key, value in ntfs_info.items():

            print(
                f"{key}: {value}",
                file=sys.stderr
            )

        self.cluster_size = ntfs_info["cluster_size"]
        self.total_clusters = ntfs_info["total_clusters"]
        

        if self.cluster_size <= 0:
            raise Exception(
                "Invalid NTFS cluster size"
            )

        print(
            "\nCluster Size:",
            self.cluster_size,
            file=sys.stderr
        )

        # -----------------------------------------------------
        # MFT RECORD SIZE
        # -----------------------------------------------------

        record_size_raw = (
            ntfs_info["clusters_per_file_record"]
        )

        if record_size_raw < 0:

            self.record_size = (
                2 ** abs(record_size_raw)
            )

        else:

            self.record_size = (
                record_size_raw
                *
                self.cluster_size
            )

        if self.record_size <= 0:
            raise Exception(
                "Invalid MFT record size"
            )

        print(
            "MFT Record Size:",
            self.record_size,
            file=sys.stderr
        )

        # -----------------------------------------------------
        # MFT START OFFSET
        # -----------------------------------------------------

        self.mft_offset = (
            self.volume_offset
            + ntfs_info["mft_cluster"] * self.cluster_size
        )

        print(
            "MFT Offset:",
            self.mft_offset,
            file=sys.stderr
        )

        self.ntfs_info = ntfs_info

        # -----------------------------------------------------
        # DETERMINE ACTUAL MFT SIZE
        # -----------------------------------------------------

        self.determine_mft_geometry()

        return ntfs_info

    # ---------------------------------------------------------
    # MFT GEOMETRY
    # ---------------------------------------------------------

    def determine_mft_geometry(self):

        print(
            "\nDetermining actual $MFT geometry...",
            file=sys.stderr
        )

        # -----------------------------------------------------
        # Read MFT record 0.
        #
        # NTFS record 0 is $MFT itself.
        # -----------------------------------------------------

        record = self.read_record(0)

        if record is None:
            raise Exception(
                "Unable to read MFT record 0"
            )

        if len(record) != self.record_size:
            raise Exception(
                "Incomplete MFT record 0"
            )

        if not is_valid_mft_record(record):

            raise Exception(
                "MFT record 0 is not a valid FILE record"
            )

        try:

            record = apply_fixup(record)

        except Exception as error:

            raise Exception(
                f"Failed to apply MFT record 0 fixup: {error}"
            )

        try:

            header = parse_mft_header(record)

        except Exception as error:

            raise Exception(
                f"Failed to parse MFT record 0 header: {error}"
            )

        if header["record_number"] != 0:

            raise Exception(
                "MFT record 0 has an unexpected record number"
            )

        print(
            "MFT record 0 validated",
            file=sys.stderr
        )

        # -----------------------------------------------------
        # Parse attributes in record 0.
        # -----------------------------------------------------

        try:

            attributes = parse_attributes(
                record,
                header["first_attribute_offset"]
            )

        except Exception as error:

            raise Exception(
                f"Failed to parse $MFT attributes: {error}"
            )

        mft_data_attribute = None

        for attribute in attributes:

            if attribute["type"] != "$DATA":
                continue

            # The unnamed $DATA stream belongs to $MFT.
            #
            # Named DATA streams are not the primary MFT stream.
            if attribute["stream_name"]:
                continue

            mft_data_attribute = attribute

            break

        if mft_data_attribute is None:

            raise Exception(
                "Unable to locate unnamed $DATA attribute "
                "for $MFT record 0"
            )

        if mft_data_attribute["resident"] == 0:

            raise Exception(
                "$MFT $DATA attribute is unexpectedly resident"
            )

        # -----------------------------------------------------
        # Parse the non-resident $DATA attribute.
        # -----------------------------------------------------

        mft_data = parse_non_resident_attribute(
            record,
            mft_data_attribute
        )

        self.mft_size = mft_data["real_size"]

        self.mft_allocated_size = (
            mft_data["allocated_size"]
        )

        if self.mft_size <= 0:

            raise Exception(
                f"Invalid $MFT real size: {self.mft_size}"
            )

        # -----------------------------------------------------
        # Parse MFT data runs.
        #
        # We store these now because later stages will need
        # them for allocation / cluster ownership analysis.
        # -----------------------------------------------------

        self.mft_data_runs = parse_data_runs(
            record,
            mft_data["runs_start"],
            mft_data_attribute["offset"] + mft_data_attribute["length"],
        )

        # -----------------------------------------------------
        # From here on, records are located through $MFT's own
        # data runs, so a fragmented MFT is read correctly.
        # -----------------------------------------------------

        self.mft_locator = MftRecordLocator(
            data_runs=self.mft_data_runs,
            geometry=self.geometry,
            record_size=self.record_size,
            mft_size=self.mft_size,
        )

        first_run = self.mft_data_runs[0]
        if first_run.get("lcn") != self.ntfs_info["mft_cluster"]:
            self._warn(
                "The boot sector's MFT cluster "
                f"({self.ntfs_info['mft_cluster']}) does not match the "
                f"first $MFT data run ({first_run.get('lcn')})"
            )

        if self.mft_locator.mapped_bytes < self.mft_size:
            # The rest of the runs live in an $ATTRIBUTE_LIST extension
            # record, which this parser does not follow yet.
            self._warn(
                "$MFT data runs cover only "
                f"{self.mft_locator.mapped_bytes} of {self.mft_size} bytes; "
                "records beyond that point were not read"
            )

        # -----------------------------------------------------
        # Calculate actual number of MFT records.
        #
        # We use CEILING because the MFT stream may not end
        # exactly on a record boundary, but never count records
        # the data runs do not map.
        # -----------------------------------------------------

        self.mft_record_count = min(
            math.ceil(self.mft_size / self.record_size),
            self.mft_locator.mapped_bytes // self.record_size,
        )

        if self.mft_record_count <= 0:

            raise Exception(
                "Calculated MFT record count is invalid"
            )

        print(
            "\nActual $MFT Geometry",
            file=sys.stderr
        )

        print(
            "MFT Real Size:",
            self.mft_size,
            "bytes",
            file=sys.stderr
        )

        print(
            "MFT Allocated Size:",
            self.mft_allocated_size,
            "bytes",
            file=sys.stderr
        )

        print(
            "MFT Record Size:",
            self.record_size,
            "bytes",
            file=sys.stderr
        )

        print(
            "MFT Record Count:",
            self.mft_record_count,
            file=sys.stderr
        )

        print(
            "MFT Data Runs:",
            len(self.mft_data_runs),
            file=sys.stderr
        )

        for run in self.mft_data_runs:

            print(
                "  Run:",
                run,
                file=sys.stderr
            )

        return {
            "mft_offset": self.mft_offset,
            "mft_size": self.mft_size,
            "mft_allocated_size": self.mft_allocated_size,
            "record_size": self.record_size,
            "record_count": self.mft_record_count,
            "data_runs": self.mft_data_runs,
        }

    # ---------------------------------------------------------
    # READ MFT RECORD
    # ---------------------------------------------------------

    def read_record(
        self,
        record_number
    ):

        if record_number < 0:

            raise ValueError(
                "MFT record number cannot be negative"
            )

        if self.mft_offset is None:

            raise Exception(
                "MFT offset has not been initialized"
            )

        if self.record_size is None:

            raise Exception(
                "MFT record size has not been initialized"
            )

        if self.mft_locator is not None:
            return self.mft_locator.read(self.image, record_number)

        # Before $MFT's data runs are known (i.e. while reading record 0),
        # the boot sector's MFT start is the only location available.
        # Record 0 is always at that location.
        return read_mft_record(
            self.image,
            self.mft_offset,
            record_number,
            self.record_size
        )

    # ---------------------------------------------------------
    # VALIDATE MFT RECORD
    # ---------------------------------------------------------

    def validate_record(
        self,
        record
    ):

        if record is None:
            return False

        if len(record) != self.record_size:
            return False

        if record == b"\x00" * self.record_size:
            return False

        if not is_valid_mft_record(record):
            return False

        return True

    # ---------------------------------------------------------
    # PARSE RECORD HEADER
    # ---------------------------------------------------------

    def parse_record_header(
        self,
        record
    ):

        record = apply_fixup(record)

        return parse_mft_header(record), record

    # ---------------------------------------------------------
    # GET SINGLE EVIDENCE RECORD
    # ---------------------------------------------------------

    def get_evidence(
        self,
        record_number
    ):

        record = self.read_record(
            record_number
        )

        if not self.validate_record(record):
            return None

        try:

            header, record = self.parse_record_header(
                record
            )

            return self.record_processor.process_record(
                header,
                record
            )

        except Exception as error:

            raise ValueError(
                f"MFT record {record_number} is malformed: {error}"
            ) from error

    # ---------------------------------------------------------
    # ENUMERATE COMPLETE MFT
    # ---------------------------------------------------------

    def enumerate_records(
        self,
        total_records=None
    ):
        
        if total_records is None:

            if self.mft_record_count is None:
                raise Exception(
                    "MFT geometry has not been determined"
                )

            total_records = self.mft_record_count

        if total_records <= 0:
            raise ValueError(
                "MFT enumeration count must be greater than zero"
            )

        # Never allow enumeration beyond the actual MFT.
        if self.mft_record_count is not None:
            total_records = min(
                total_records,
                self.mft_record_count
            )

        # ---------------------------------------------------------
        # Reset MFT classification counters.
        #
        # This makes repeated enumeration deterministic.
        # ---------------------------------------------------------

        self.mft_slots = total_records
        self.allocated_records = 0
        self.deleted_records = 0
        self.unused_records = 0
        self.corrupt_records = 0
        self.record_errors = []
        self.record_error_count = 0

        print(
            "\nEnumerating MFT records:",
            total_records,
            file=sys.stderr
        )

        for record_number in range(total_records):

            progress.report("Reading MFT records", record_number + 1, total_records)

            record = self.read_record(
                record_number
            )

            # -----------------------------------------------------
            # CLASSIFY MFT SLOT
            # -----------------------------------------------------

            classification = classify_mft_record(
                record
            )

            state = classification["state"]

            if state == "ALLOCATED":
                self.allocated_records += 1

            elif state == "DELETED":
                self.deleted_records += 1

            elif state == "UNUSED":
                self.unused_records += 1

            elif state == "CORRUPT":
                self.corrupt_records += 1

            # -----------------------------------------------------
            # Only allocated/deleted records are evidence records.
            #
            # UNUSED and CORRUPT records are not sent into the
            # existing EvidenceObject pipeline yet.
            # -----------------------------------------------------

            if state not in ("ALLOCATED", "DELETED"):
                continue

            # -----------------------------------------------------
            # Parse the record. A malformed record must never stop
            # the analysis: it is reported and counted as corrupt.
            # -----------------------------------------------------

            try:

                header, record = self.parse_record_header(
                    record
                )

                evidence = self.record_processor.process_record(
                    header,
                    record
                )

            except Exception as error:

                # Correct the counters because the initial classifier
                # considered the structure usable.
                if state == "ALLOCATED":
                    self.allocated_records -= 1
                elif state == "DELETED":
                    self.deleted_records -= 1

                self.corrupt_records += 1

                self._record_error(record_number, error)

                continue

            self.record_processor.total_records += 1

            self.record_processor._update_statistics(
                evidence
            )

            self.record_processor.evidence_objects.append(
                evidence
            )

        # ---------------------------------------------------------
        # Path reconstruction should happen after the complete
        # MFT has been collected, not once for every record.
        # ---------------------------------------------------------

        self.record_processor.reconstruct_paths()

        self.allocation_ranges = self.analyze_allocation()

        print("\nNTFS Allocation Analysis")

        allocated_clusters = 0
        unallocated_clusters = 0

        for item in self.allocation_ranges:

            if item["state"] == "allocated":
                allocated_clusters += item["cluster_count"]

            elif item["state"] == "unallocated":
                unallocated_clusters += item["cluster_count"]

        print("Allocation ranges:", len(self.allocation_ranges))
        print("Allocated clusters:", allocated_clusters)
        print("Unallocated clusters:", unallocated_clusters)

        print("\nUnallocated Byte Ranges", file=sys.stderr)

        for item in self.get_unallocated_ranges():

            print(
                f"  Clusters {item['start_cluster']}"
                f"-{item['end_cluster']} | "
                f"Offset {item['start_offset']}"
                f"-{item['end_offset'] - 1} | "
                f"Bytes {item['byte_count']}",
                file=sys.stderr
            )

        # ---------------------------------------------------------
        # Existing evidence statistics
        # ---------------------------------------------------------

        statistics = self.record_processor.build_statistics()

        # ---------------------------------------------------------
        # Add MFT-level forensic classification statistics.
        # ---------------------------------------------------------

        statistics.update({
            "mft_slots": self.mft_slots,
            "allocated_records": self.allocated_records,
            "deleted_records": self.deleted_records,
            "unused_records": self.unused_records,
            "corrupt_records": self.corrupt_records,
            "record_error_count": self.record_error_count,
            "record_errors": list(self.record_errors),
            "warnings": list(self.warnings),
        })

        print(
            "\nMFT Record Classification",
            file=sys.stderr
        )

        print(
            "  MFT Slots:",
            self.mft_slots,
            file=sys.stderr
        )

        print(
            "  Allocated Records:",
            self.allocated_records,
            file=sys.stderr
        )

        print(
            "  Deleted Records:",
            self.deleted_records,
            file=sys.stderr
        )

        print(
            "  Unused Records:",
            self.unused_records,
            file=sys.stderr
        )

        print(
            "  Corrupt Records:",
            self.corrupt_records,
            file=sys.stderr
        )

        return statistics

    def load_allocation(self):
        """
        Decode the NTFS $Bitmap without enumerating the whole MFT.

        Reads only MFT record 6, so commands that need cluster
        allocation (free-space listing, carving) stay fast on large
        volumes. parse_boot_sector() must have been called first.

        Returns:
            List of allocation ranges (also stored on the parser).
        """

        bitmap_evidence = self.get_evidence(BITMAP_RECORD)

        self.allocation_ranges = self.analyze_allocation(bitmap_evidence)

        return self.allocation_ranges

    def analyze_allocation(self, bitmap_evidence=None):
        """
        Read and decode the NTFS $Bitmap.

        Args:
            bitmap_evidence: the parsed $Bitmap record. When omitted it
                is taken from the records collected by enumerate_records().

        Returns:
            List of allocation ranges.
        """

        if bitmap_evidence is None:
            for evidence in self.record_processor.evidence_objects:
                if evidence.record_number == BITMAP_RECORD:
                    bitmap_evidence = evidence
                    break

        if (
            bitmap_evidence is not None
            and bitmap_evidence.filename != "$Bitmap"
        ):
            raise RuntimeError(
                f"MFT record {BITMAP_RECORD} is "
                f"{bitmap_evidence.filename!r}, not $Bitmap"
            )

        if bitmap_evidence is None:
            raise RuntimeError(
                "NTFS $Bitmap record was not found"
            )

        if not bitmap_evidence.data_runs:
            raise RuntimeError(
                "NTFS $Bitmap has no data runs"
            )

        bitmap_size = bitmap_evidence.file_size

        bitmap_data = load_bitmap(
            image=self.image,
            bitmap_runs=bitmap_evidence.data_runs,
            cluster_size=self.cluster_size,
            bitmap_size=bitmap_size,
            volume_offset=self.volume_offset,
        )

        total_clusters = self.total_clusters

        if total_clusters is None or total_clusters <= 0:
            raise RuntimeError(
                "Invalid NTFS volume cluster count"
            )

        allocation_ranges = decode_bitmap(
            bitmap_data=bitmap_data,
            total_clusters=total_clusters
        )

        return allocation_ranges

    
        
    def get_unallocated_ranges(self):
        """Return validated unallocated NTFS ranges with half-open byte offsets."""

        if self.ntfs_info is None or self.cluster_size is None:
            raise RuntimeError("Parse the NTFS boot sector before reading ranges")

        if not isinstance(self.total_clusters, int) or self.total_clusters <= 0:
            raise RuntimeError("Invalid NTFS volume cluster count")

        if not isinstance(self.volume_offset, int) or self.volume_offset < 0:
            raise ValueError("volume_offset must be a non-negative integer")

        volume_size = self.ntfs_info.get("volume_size_bytes")
        if not isinstance(volume_size, int) or volume_size <= 0:
            raise RuntimeError("Invalid NTFS volume size")

        volume_end = self.volume_offset + volume_size  # exclusive
        expected_volume_size = self.total_clusters * self.cluster_size

        if expected_volume_size > volume_size:
            raise ValueError("Cluster geometry exceeds NTFS volume size")

        current_position = self.image.tell()
        try:
            self.image.seek(0, 2)
            image_size = self.image.tell()
        finally:
            self.image.seek(current_position)

        if volume_end > image_size:
            raise ValueError("NTFS volume extends beyond the image file bounds")

        ranges = []

        for item in self.allocation_ranges:
            if item.get("state") != "unallocated":
                continue

            start_cluster = item["start_cluster"]
            end_cluster = item["end_cluster"]
            cluster_count = item["cluster_count"]

            if not all(isinstance(value, int) for value in (
                start_cluster, end_cluster, cluster_count
            )):
                raise ValueError("Allocation range fields must be integers")

            if (
                start_cluster < 0
                or end_cluster < start_cluster
                or end_cluster >= self.total_clusters
                or cluster_count != end_cluster - start_cluster + 1
            ):
                raise ValueError("Invalid unallocated cluster bounds")

            start_offset = (
                self.volume_offset + start_cluster * self.cluster_size
            )
            end_offset = (
                self.volume_offset + (end_cluster + 1) * self.cluster_size
            )
            byte_count = cluster_count * self.cluster_size

            if end_offset > volume_end or end_offset > image_size:
                raise ValueError("Unallocated range exceeds image or volume bounds")

            if end_offset - start_offset != byte_count:
                raise ValueError("Invalid unallocated byte-range size")

            ranges.append({
                "start_cluster": start_cluster,
                "cluster_count": cluster_count,
                "end_cluster": end_cluster,  # inclusive
                "start_offset": start_offset,
                "end_offset": end_offset,    # exclusive
                "byte_count": byte_count,
                "state": "unallocated",
            })

        return ranges


    def get_unallocated_regions(self):
        """Convert allocation dictionaries into validated region models."""

        regions = []

        for item in self.get_unallocated_ranges():
            regions.append(
                UnallocatedRegion(
                    start_cluster=item["start_cluster"],
                    end_cluster=item["end_cluster"],
                    cluster_count=item["cluster_count"],
                    start_offset=item["start_offset"],
                    end_offset=item["end_offset"],
                    byte_count=item["byte_count"],
                    state="UNALLOCATED",
                )
            )

        return regions

    def test_unallocated_reader(self, regions):
        """
        Test sequential reading of unallocated space.

        Reads only a small number of chunks to verify that
        unallocated ranges can be accessed safely.
        """

        ranges = self.get_unallocated_ranges()

        reader = UnallocatedReader(
            image=self.image,
            ranges=regions,
            cluster_size=self.cluster_size,
            chunk_size=1024 * 1024
        )

        chunk_count = 0
        total_bytes = 0

        for chunk in reader.iter_chunks():

            chunk_count += 1
            total_bytes += chunk["size"]

            if chunk_count <= 3:
                print(
                    "Unallocated reader chunk:",
                    f"offset={chunk['offset']}",
                    f"size={chunk['size']}",
                    f"clusters="
                    f"{chunk['start_cluster']}-"
                    f"{chunk['end_cluster']}"
                )

            if chunk_count >= 3:
                break

        print(
            "Unallocated reader test:",
            f"chunks={chunk_count}",
            f"bytes={total_bytes}"
        )

    def test_unallocated_scanner(self, regions):
        """
        Test scanning unallocated space using fixed-size windows.
        """

        ranges = self.get_unallocated_ranges()

        reader = UnallocatedReader(
            image=self.image,
            ranges=regions,
            cluster_size=self.cluster_size,
            chunk_size=1024 * 1024
        )

        scanner = UnallocatedScanner(
            reader=reader,
            window_size=64 * 1024
        )

        window_count = 0
        total_bytes = 0

        for window in scanner.scan():

            window_count += 1
            total_bytes += window["size"]

            if window_count <= 3:
                print(
                    "Unallocated scanner window:",
                    f"offset={window['offset']}",
                    f"size={window['size']}"
                )

            if window_count >= 3:
                break

        print(
            "Unallocated scanner test:",
            f"windows={window_count}",
            f"bytes={total_bytes}"
        )
    # ---------------------------------------------------------
    # DIAGNOSTICS
    # ---------------------------------------------------------

    def _warn(self, message):

        self.warnings.append(message)

        print(f"WARNING: {message}", file=sys.stderr)

    def _record_error(self, record_number, error):

        self.record_error_count += 1

        message = f"{type(error).__name__}: {error}"

        if len(self.record_errors) < MAX_RECORD_ERRORS:
            self.record_errors.append({
                "record_number": record_number,
                "error": message,
            })

        print(
            f"Skipped malformed MFT record {record_number}: {message}",
            file=sys.stderr
        )

    # ---------------------------------------------------------
    # PROPERTIES
    # ---------------------------------------------------------

    @property
    def index_block_size(self):
        """Size of one INDX block in directory indexes ($INDEX_ALLOCATION)."""

        encoded = self.ntfs_info["clusters_per_index_buffer"]

        if encoded < 0:
            return 1 << -encoded

        return encoded * self.cluster_size

    @property
    def geometry(self):
        """Volume location and cluster size; see VolumeGeometry."""

        if self.cluster_size is None:
            raise RuntimeError(
                "Parse the NTFS boot sector before using volume geometry"
            )

        return VolumeGeometry(
            volume_offset=self.volume_offset,
            cluster_size=self.cluster_size,
            total_clusters=self.total_clusters,
        )

    @property
    def evidence_objects(self):

        return self.record_processor.evidence_objects

    @property
    def allocation(self):

        return self.allocation_ranges

    @property
    def image_handle(self):

        return self.image

    @property
    def unallocated_region_service(self):
        """
        Return a service for accessing validated unallocated regions.

        The service is created from the parser's current allocation
        state and forensic image handle.
        """

        regions = self.get_unallocated_regions()

        return UnallocatedRegionService(
            image=self.image,
            regions=regions,
            cluster_size=self.cluster_size,
        )