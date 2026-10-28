import struct

def parse_resident_attribute(record, attribute):

    offset = attribute["offset"]

    content_size = struct.unpack("<I", record[offset + 16 : offset + 20])[0]

    content_offset = struct.unpack("<H", record[offset + 20 : offset + 22])[0]

    indexed_flag = record[offset + 22]

    content_start = offset + content_offset

    content_end = content_start + content_size

    content = record[content_start : content_end]

    return {
        "content_size": content_size,
        "content_offset": content_offset,
        "is_indexed": indexed_flag == 1,
        "content_start": content_start,
        "content_end": content_end,
        "storage_type": "Resident",
        "content": content
    }