import struct
from time_utils import filetime_to_datetime

def parse_standard_information(content):

    created_time = struct.unpack(
        "<Q",
        content[0:8]
    )[0]

    modified_time = struct.unpack(
        "<Q",
        content[8:16]
    )[0]

    mft_modified_time = struct.unpack(
        "<Q",
        content[16:24]
    )[0]

    accessed_time = struct.unpack(
        "<Q",
        content[24:32]
    )[0]

    return {

        "created_time":
            filetime_to_datetime(created_time),

        "modified_time":
            filetime_to_datetime(modified_time),

        "mft_modified_time":
            filetime_to_datetime(mft_modified_time),

        "accessed_time":
            filetime_to_datetime(accessed_time)
    }