import sys

from attributes import parse_attributes

from resident import parse_resident_attribute
from non_resident import (
    parse_non_resident_attribute,
    parse_data_runs
)

from standard_information import parse_standard_information
from file_name import parse_file_name

from evidence_object import EvidenceObject

from path_reconstruction import (
    build_record_database,
    add_record,
    reconstruct_path,
    validate_parent_reference,
)


# $FILE_NAME namespace preference (higher wins): 1 Win32, 3 Win32+DOS,
# 0 POSIX, 2 DOS (generated 8.3 alias).
FILE_NAME_NAMESPACE_SCORE = {1: 3, 3: 3, 0: 2, 2: 1}


class RecordProcessor:

    def __init__(
        self,
        repository,
        case_id
    ):

        self.repository = repository
        self.case_id = case_id

        self.total_records = 0
        self.total_files = 0
        self.total_directories = 0
        self.deleted_files = 0
        self.fragmented_files = 0
        self.ads_files = 0
        self.timeline_events = 0
        self.evidence_objects = []


    def process_record(
        self,
        header,
        record
    ):

        # self.total_records += 1

        evidence = self._create_evidence(header)

        self._parse_attributes(
            record,
            header,
            evidence
        )

        # evidence.children = self.container_manager.analyze(evidence)

        # self._update_statistics(
        #     evidence
        # )

        # self.evidence_objects.append(
        #     evidence
        # )

        return evidence

    def _create_evidence(
        self,
        header
    ):

        evidence = EvidenceObject()

        # ---------------------------------------------------------
        # Core MFT identity
        # ---------------------------------------------------------

        evidence.record_number = header["record_number"]

        evidence.sequence_number = header["sequence_number"]

        evidence.flags = header["flags"]

        # ---------------------------------------------------------
        # MFT record allocation state
        # ---------------------------------------------------------

        evidence.in_use = bool(
            header["flags"] & 0x01
        )

        evidence.deleted = not evidence.in_use

        # ---------------------------------------------------------
        # Directory / file classification
        # ---------------------------------------------------------

        evidence.directory = bool(
            header["flags"] & 0x02
        )

        # ---------------------------------------------------------
        # MFT record sizes
        #
        # These are the sizes of the MFT record itself, NOT the
        # file's DATA allocation.
        # ---------------------------------------------------------

        evidence.used_size = header["used_size"]

        evidence.record_allocated_size = (
            header["allocated_size"]
        )

        # ---------------------------------------------------------
        # Explicit forensic classification
        #
        # At this point RecordProcessor receives only records that
        # have already been classified by NTFSParser as either
        # ALLOCATED or DELETED.
        # ---------------------------------------------------------

        if evidence.in_use:

            evidence.mft_state = "ALLOCATED"

        else:

            evidence.mft_state = "DELETED"

        # ---------------------------------------------------------
        # Existing application-level record type
        # ---------------------------------------------------------

        evidence.record_type = (
            "Directory"
            if evidence.directory
            else "File"
        )

        return evidence
    
    def _parse_attributes(
    self,
    record,
    header,
    evidence
):

        attributes = parse_attributes(
            record,
            header["first_attribute_offset"]
        )

        for attribute in attributes:

            attribute_type = attribute["type"]

            # Resident attribute
            if attribute["resident"] == 0:

                resident = parse_resident_attribute(
                    record,
                    attribute
                )

                content = resident["content"]

            # Non Resident attribute
            else:

                resident = parse_non_resident_attribute(
                    record,
                    attribute
                )

                content = resident

            if attribute_type == "$STANDARD_INFORMATION":

                self._process_standard_information(
                    evidence,
                    content
                )

            elif attribute_type == "$FILE_NAME":

                self._process_file_name(
                    evidence,
                    content
                )

            elif attribute_type == "$DATA":

                self._process_data_attribute(
                    evidence,
                    attribute,
                    resident,
                    record
                )
    
    def _process_standard_information(
    self,
    evidence,
    content
):

        info = parse_standard_information(
            content
        )

        evidence.created_time = info["created_time"]

        evidence.modified_time = info["modified_time"]

        evidence.accessed_time = info["accessed_time"]

        evidence.mft_modified_time = info[
            "mft_modified_time"
        ]
    
    def _process_file_name(
    self,
    evidence,
    content
):

        info = parse_file_name(
            content
        )

        # A record can carry several $FILE_NAMEs (long name, 8.3 alias,
        # hard links). Keep the most readable one: Win32 > POSIX > DOS.
        score = FILE_NAME_NAMESPACE_SCORE.get(info["namespace"], 0)

        if score < evidence.file_name_score:
            return

        evidence.file_name_score = score

        evidence.parent_record = info[
            "parent_record_number"
        ]

        evidence.parent_sequence_number = info[
            "parent_sequence_number"
        ]

        evidence.filename = info[
            "filename"
        ]

        evidence.file_size = info[
            "real_size"
        ]

        evidence.allocated_size = info[
            "allocated_size"
        ]

        #
        # FILE_NAME timestamps are useful for comparison.
        # Prefer STANDARD_INFORMATION if already present.
        #

        if evidence.created_time is None:
            evidence.created_time = info[
                "created_time"
            ]

        if evidence.modified_time is None:
            evidence.modified_time = info[
                "modified_time"
            ]

        if evidence.accessed_time is None:
            evidence.accessed_time = info[
                "accessed_time"
            ]

        if evidence.mft_modified_time is None:
            evidence.mft_modified_time = info[
                "mft_modified_time"
            ]
    
    def _process_data_attribute(
    self,
    evidence,
    attribute,
    storage,
    record
):
        #
        # Detect Alternate Data Stream
        #
        if attribute["stream_name"]:

            evidence.ads_streams.append({

                "name": attribute["stream_name"],

                "attribute_id": attribute["attribute_id"]
            })

            return

        #
        # Resident DATA
        #
        if attribute["resident"] == 0:

            evidence.record_type = "Resident"

            evidence.resident_data = storage["content"]

            evidence.file_size = max(
                evidence.file_size,
                len(storage["content"])
            )

            return

        #
        # Non Resident DATA
        #
        runs = parse_data_runs(
            record,
            storage["runs_start"],
            # Runs must not be read past the end of their attribute.
            attribute["offset"] + attribute["length"],
        )

        evidence.data_runs = runs

        evidence.allocated_size = storage["allocated_size"]

        evidence.file_size = storage["real_size"]

        evidence.slack_space = (

            storage["allocated_size"]

            -

            storage["real_size"]
        )

        #
        # Fragmentation
        #
        evidence.fragment_count = len(runs)

        evidence.fragmented = (

            len(runs) > 1
        )

        if evidence.file_size > 0:

            evidence.fragment_ratio = (

                evidence.fragment_count

                /

                evidence.file_size

            )
    
    def _update_statistics(
    self,
    evidence
):

        if evidence.directory:

            self.total_directories += 1

        else:

            self.total_files += 1

        if evidence.deleted:

            self.deleted_files += 1

        if evidence.fragmented:

            self.fragmented_files += 1

        if evidence.ads_streams:

            self.ads_files += 1

        self.timeline_events += len(
            evidence.timeline_events
        )
    

    def _save_evidence(
    self,
    evidence
):

        self.repository.insert_evidence(

            self.case_id,

            evidence
        )
    
    def build_statistics(self):

        return {

            "total_records": self.total_records,

            "total_files": self.total_files,

            "total_directories": self.total_directories,

            "deleted_files": self.deleted_files,

            "fragmented_files": self.fragmented_files,

            "ads_files": self.ads_files,

            "timeline_events": self.timeline_events
        }
    
    def build_record_database(self):

        database = build_record_database()

        for evidence in self.evidence_objects:

            add_record(

                database,

                record_number=evidence.record_number,

                filename=evidence.filename,

                size=evidence.file_size,

                allocated_size=evidence.allocated_size,

                parent_record_number=evidence.parent_record,

                parent_sequence_number=evidence.parent_sequence_number,

                sequence_number=evidence.sequence_number,

                deleted=evidence.deleted,

                is_directory=evidence.directory,

                fragment_count=evidence.fragment_count,

                fragmented=evidence.fragmented,

                fragment_ratio=evidence.fragment_ratio,

                slack_space=evidence.slack_space,

                created_time=evidence.created_time,

                modified_time=evidence.modified_time,

                accessed_time=evidence.accessed_time,

                mft_modified_time=evidence.mft_modified_time,

            )

        return database
    
    def reconstruct_paths(self):

        database = self.build_record_database()

        for evidence in self.evidence_objects:

            evidence.full_path = reconstruct_path(

                database,

                evidence.record_number,

            )

        print("\nFilesystem Path Reconstruction", file=sys.stderr)

        displayed = 0

        for evidence in self.evidence_objects:
            if displayed >= 20:
                break

            print(
                f"  Record {evidence.record_number}: "
                f"{evidence.full_path}",
                file=sys.stderr
            )

            displayed += 1

        print("\nParent Reference Validation", file=sys.stderr)

        displayed = 0

        for evidence in self.evidence_objects:

            if displayed >= 20:
                break

            validation = validate_parent_reference(
                database,
                evidence.record_number,
            )

            print(
                f"  Record {evidence.record_number}: "
                f"{validation['reason']}",
                file=sys.stderr
            )

            displayed += 1

        print("\nOrphan Candidate Details", file=sys.stderr)

        for evidence in self.evidence_objects:

            if evidence.record_number not in (12, 13, 14, 15):
                continue

            print(
                f"  Record {evidence.record_number}: "
                f"name={evidence.filename!r}, "
                f"type={'DIRECTORY' if evidence.directory else 'FILE'}, "
                f"parent={evidence.parent_record}, "
                f"parent_sequence={evidence.parent_sequence_number}, "
                f"sequence={evidence.sequence_number}, "
                f"deleted={evidence.deleted}",
                file=sys.stderr
            )

        print("\nMFT Records Attribute Details", file=sys.stderr)

        for evidence in self.evidence_objects:

            if evidence.record_number not in (6, 12, 13, 14, 15):
                continue

            print(
                f"  Record {evidence.record_number}: "
                f"name={evidence.filename!r}, "
                f"parent={evidence.parent_record}, "
                f"sequence={evidence.sequence_number}, "
                f"mft_state={evidence.mft_state}, "
                f"directory={evidence.directory}, "
                f"file_size={evidence.file_size}, "
                f"allocated_size={evidence.allocated_size}, "
                f"data_runs={len(evidence.data_runs)}, "
                f"ads={len(evidence.ads_streams)}",
                file=sys.stderr
            )

    def save_all(self):

        # One transaction for all rows: a commit per row was ~10 ms each.
        self.repository.insert_evidence_many(
            self.case_id,
            self.evidence_objects
        )