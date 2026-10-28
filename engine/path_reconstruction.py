def build_record_database():
    
    return {}

def add_record(
        database,
        record_number,
        filename,
        size,
        allocated_size,
        parent_record_number,
        parent_sequence_number,
        sequence_number,
        deleted,
        is_directory,
        fragment_count=None,
        fragmented=None,
        fragment_ratio=None,
        slack_space=None,
        created_time=None,
        modified_time=None,
        accessed_time=None,
        mft_modified_time=None
):
    database[record_number] = {
        "record_number": record_number,
        "filename": filename,
        "file_size": size,
        "allocated_size": allocated_size,
        "parent_record_number": parent_record_number,
        "parent_sequence_number": parent_sequence_number,
        "sequence_number": sequence_number,
        "deleted": deleted,
        "directory": is_directory,
        "fragment_count": fragment_count,
        "fragmented": fragmented,
        "fragment_ratio": fragment_ratio,
        "slack_space": slack_space,
        "created_time": created_time,
        "modified_time": modified_time,
        "accessed_time": accessed_time,
        "mft_modified_time": mft_modified_time,
    }


def reconstruct_path(database, record_number):

    path_parts = []

    visited = set()

    current = record_number

    while current in database:

        # Loop protection
        if current in visited:
            break

        visited.add(current)

        entry = database[current]

        filename = entry["filename"]

        if filename is None:
            break

        path_parts.insert(0, str(filename))

        parent = entry["parent_record_number"]
        parent_sequence = entry["parent_sequence_number"]

        # Root/self-reference stop
        if parent == current:
            break

        # Parent does not exist
        if parent not in database:
            break

        parent_entry = database[parent]

        # Validate the NTFS file reference sequence number
        if (
            parent_sequence is not None
            and parent_entry["sequence_number"] != parent_sequence
        ):
            break

        current = parent

    if not path_parts:
        return f"[ORPHAN_RECORD_{record_number}]"

    return "/".join(path_parts)

def validate_parent_reference(database, record_number):
    
    if record_number not in database:
        return {
            "valid": False,
            "reason": "RECORD_NOT_FOUND",
            "parent_record_number": None,
            "parent_sequence_number": None,
        }

    entry = database[record_number]

    parent_record = entry["parent_record_number"]
    parent_sequence = entry["parent_sequence_number"]

    if parent_record == record_number:
        return {
            "valid": True,
            "reason": "SELF_REFERENCE_ROOT",
            "parent_record_number": parent_record,
            "parent_sequence_number": parent_sequence,
        }

    if parent_record not in database:
        return {
            "valid": False,
            "reason": "PARENT_NOT_FOUND",
            "parent_record_number": parent_record,
            "parent_sequence_number": parent_sequence,
        }

    parent_entry = database[parent_record]

    if (
        parent_sequence is not None
        and parent_entry["sequence_number"] != parent_sequence
    ):
        return {
            "valid": False,
            "reason": "PARENT_SEQUENCE_MISMATCH",
            "parent_record_number": parent_record,
            "parent_sequence_number": parent_sequence,
        }

    if not parent_entry["directory"]:
        return {
            "valid": False,
            "reason": "PARENT_NOT_DIRECTORY",
            "parent_record_number": parent_record,
            "parent_sequence_number": parent_sequence,
        }

    return {
        "valid": True,
        "reason": "VALID_PARENT",
        "parent_record_number": parent_record,
        "parent_sequence_number": parent_sequence,
    }