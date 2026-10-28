import struct 
from time_utils import filetime_to_datetime

def parse_file_name(content):


    raw_parent_reference = struct.unpack("<Q", content[0:8])[0]

    parent_reference = (raw_parent_reference & 0x0000FFFFFFFFFFFF)

    parent_sequence = (raw_parent_reference >> 48)

    created_time = struct.unpack("<Q", content[8:16])[0]

    modified_time = struct.unpack("<Q", content[16:24])[0]

    mft_modified_time = struct.unpack("<Q", content[24:32])[0]

    accessed_time = struct.unpack("<Q", content[32:40])[0]

    allocated_size = struct.unpack("<Q", content[40:48])[0]

    real_size = struct.unpack("<Q", content[48:56])[0]

    flags = struct.unpack("<I", content[56:60])[0]

    reparse_value = struct.unpack("<I", content[60:64])[0]

    filename_length = content[64]

    namespace = content[65]

    filename_raw = content[66:66 + (filename_length * 2)]

    filename = filename_raw.decode(
        "utf-16le",
        errors="ignore"
    )

    return {

        "parent_record_number": parent_reference,

        "parent_sequence_number": parent_sequence,

        "created_time":
            filetime_to_datetime(created_time),

        "modified_time":
            filetime_to_datetime(modified_time),

        "mft_modified_time":
            filetime_to_datetime(mft_modified_time),

        "accessed_time":
            filetime_to_datetime(accessed_time),

        "allocated_size": allocated_size,

        "real_size": real_size,

        "flags": flags,

        "reparse_value": reparse_value,

        "filename_length": filename_length,

        "namespace": namespace,

        "filename": filename
    }



