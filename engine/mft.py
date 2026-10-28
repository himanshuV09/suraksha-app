#Parse MFT Header
import struct 

def parse_mft_header(record):

    signature = record[0:4].decode()

    fixup_offset = struct.unpack("<H", record[4:6])[0]

    fixup_entries = struct.unpack("<H", record[6:8])[0]

    lsn = struct.unpack("<Q", record[8:16])[0]

    sequence_number = struct.unpack("<H", record[16:18])[0]

    hard_link_count = struct.unpack("<H", record[18:20])[0]

    first_attribute_offset = struct.unpack("<H", record[20:22])[0]

    flags = struct.unpack("<H", record[22:24])[0]

    used_size = struct.unpack("<I", record[24:28])[0]

    allocated_size = struct.unpack("<I", record[28:32])[0]

    record_number = struct.unpack("<I", record[44:48])[0]

    return {
        "signature": signature,
        "fixup_offset": fixup_offset,
        "fixup_entries": fixup_entries,
        "lsn": lsn,
        "sequence_number": sequence_number,
        "hard_link_count": hard_link_count,
        "first_attribute_offset": first_attribute_offset,
        "flags": flags,
        "used_size": used_size,
        "allocated_size": allocated_size,
        "record_number": record_number
    }