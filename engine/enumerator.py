import struct


def read_mft_record(image_file, mft_offset, record_number, record_size):
    offset = mft_offset + (record_number * record_size)

    image_file.seek(offset)

    record = image_file.read(record_size)

    return record


def is_valid_mft_record(record):
    if len(record) < 4:
        return False

    return record[0:4] == b"FILE"


def get_record_state(flags):
    states = []

    if flags & 0x01:
        states.append("IN_USE")
    else:
        states.append("DELETED")

    if flags & 0x02:
        states.append("DIRECTORY")
    else:
        states.append("FILE")

    return states


def classify_mft_record(record):
    """
    Classify an MFT slot without modifying the record.

    Possible states:

        UNUSED
        CORRUPT
        ALLOCATED
        DELETED
    """

    if not record:
        return {
            "state": "UNUSED",
            "reason": "Empty MFT slot",
        }

    if len(record) < 48:
        return {
            "state": "CORRUPT",
            "reason": "MFT record is smaller than the NTFS header",
        }

    signature = record[0:4]

    # Completely unused MFT slot.
    #
    # We deliberately distinguish this from a deleted FILE record.
    if signature == b"\x00\x00\x00\x00":
        return {
            "state": "UNUSED",
            "reason": "MFT slot contains no FILE signature",
        }

    # NTFS MFT records must begin with FILE.
    if signature != b"FILE":
        return {
            "state": "UNUSED",
            "reason": "MFT slot does not contain a FILE signature",
        }

    try:
        sequence_number = struct.unpack(
            "<H",
            record[16:18]
        )[0]

        first_attribute_offset = struct.unpack(
            "<H",
            record[20:22]
        )[0]

        flags = struct.unpack(
            "<H",
            record[22:24]
        )[0]

        used_size = struct.unpack(
            "<I",
            record[24:28]
        )[0]

        allocated_size = struct.unpack(
            "<I",
            record[28:32]
        )[0]

        record_number = struct.unpack(
            "<I",
            record[44:48]
        )[0]

    except struct.error as error:
        return {
            "state": "CORRUPT",
            "reason": f"Unable to parse MFT header: {error}",
        }

    # Basic structural validation.
    #
    # These checks are deliberately conservative. We do not yet
    # attempt complete attribute validation here.
    if allocated_size == 0:
        return {
            "state": "CORRUPT",
            "reason": "MFT allocated size is zero",
        }

    if used_size == 0:
        return {
            "state": "CORRUPT",
            "reason": "MFT used size is zero",
        }

    if used_size > allocated_size:
        return {
            "state": "CORRUPT",
            "reason": "MFT used size exceeds allocated size",
        }

    if allocated_size > len(record):
        return {
            "state": "CORRUPT",
            "reason": "MFT allocated size exceeds record buffer",
        }

    if first_attribute_offset < 24:
        return {
            "state": "CORRUPT",
            "reason": "Invalid first attribute offset",
        }

    if first_attribute_offset >= used_size:
        return {
            "state": "CORRUPT",
            "reason": "First attribute offset is outside used record area",
        }

    directory = bool(flags & 0x02)
    in_use = bool(flags & 0x01)

    if in_use:
        state = "ALLOCATED"
    else:
        state = "DELETED"

    return {
        "state": state,
        "reason": "Valid NTFS MFT record",
        "record_number": record_number,
        "sequence_number": sequence_number,
        "flags": flags,
        "in_use": in_use,
        "deleted": not in_use,
        "directory": directory,
        "used_size": used_size,
        "allocated_size": allocated_size,
        "first_attribute_offset": first_attribute_offset,
    }