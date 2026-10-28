import struct

def apply_fixup(record):

    usa_offset = struct.unpack("<H", record[4:6])[0]

    usa_count = struct.unpack("<H", record[6:8])[0]

    update_sequence = record[usa_offset:usa_offset + 2]

    fixed_record = bytearray(record)

    for i in range(1, usa_count):
        
        sector_end = (i * 512) - 2

        expected = fixed_record[sector_end:sector_end + 2]

        if expected != update_sequence:
            
            raise ValueError("USA Fixup validation failed")
        
        replacement = record[usa_offset + (i * 2):usa_offset + (i * 2) + 2]

        fixed_record[sector_end:sector_end + 2] = replacement  

    return bytes(fixed_record)



