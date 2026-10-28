import struct

ATTRIBUTE_TYPES = {
    0x10: "$STANDARD_INFORMATION",
    0x20: "$ATTRIBUTE_LIST",
    0x30: "$FILE_NAME",
    0x40: "$OBJECT_ID",
    0x50: "$SECURITY_DESCRIPTOR",
    0x60: "$VOLUME_NAME",
    0x70: "$VOLUME_INFORMATION",
    0x80: "$DATA",
    0x90: "$INDEX_ROOT",
    0xA0: "$INDEX_ALLOCATION",
    0xB0: "$BITMAP",
    0xC0: "$REPARSE_POINT",
    0xD0: "$EA_INFORMATION",
    0xE0: "$EA",
    0xF0: "$PROPERTY_SET",
    0x100: "$LOGGED_UTILITY_STREAM"
}

END_MARKER = 0xFFFFFFFF

# Every attribute starts with a 16-byte common header.
ATTRIBUTE_HEADER_SIZE = 16


class AttributeParseError(ValueError):
    """An MFT record's attribute list is structurally invalid."""


def parse_attributes(record, start_offset, end_offset=None):
    """Walk the attribute headers of one (fixed-up) MFT record.

    Args:
        record: the record bytes.
        start_offset: offset of the first attribute.
        end_offset: stop looking past this offset; defaults to the end
            of the record.

    Raises:
        AttributeParseError: the list is malformed (bad length, runs past
            the end of the record, or has no end marker). Without these
            checks a zero-length attribute would loop forever.
    """

    limit = len(record) if end_offset is None else min(end_offset, len(record))

    attributes = []
    offset = start_offset

    while True:

        if offset + 4 > limit:
            raise AttributeParseError(
                "Attribute list has no end marker before the end of the "
                f"record (offset {offset})"
            )

        attribute_type = struct.unpack_from("<I", record, offset)[0]

        # End marker
        if attribute_type == END_MARKER:
            break

        if offset + ATTRIBUTE_HEADER_SIZE > limit:
            raise AttributeParseError(
                f"Attribute header at offset {offset} is truncated"
            )

        attribute_length = struct.unpack_from("<I", record, offset + 4)[0]

        if attribute_length < ATTRIBUTE_HEADER_SIZE:
            raise AttributeParseError(
                f"Attribute at offset {offset} has invalid length "
                f"{attribute_length}"
            )

        if offset + attribute_length > limit:
            raise AttributeParseError(
                f"Attribute at offset {offset} (length {attribute_length}) "
                "extends past the end of the record"
            )

        resident_flag = record[offset + 8]
        name_length = record[offset + 9]
        name_offset = struct.unpack_from("<H", record, offset + 10)[0]
        flags = struct.unpack_from("<H", record, offset + 12)[0]
        attribute_id = struct.unpack_from("<H", record, offset + 14)[0]

        # Parse attribute name (ADS name, stream name, etc.)

        attribute_stream_name = ""

        if name_length > 0:
            name_start = offset + name_offset
            name_end = name_start + (name_length * 2)

            attribute_stream_name = record[name_start:name_end].decode(
                "utf-16le",
                errors="ignore",
            )

        attribute_name = ATTRIBUTE_TYPES.get(
            attribute_type,
            hex(attribute_type)
        )

        attributes.append({

            "type": attribute_name,
            "type_code": hex(attribute_type),
            "stream_name": attribute_stream_name,
            "length": attribute_length,
            "resident": resident_flag,
            "name_length": name_length,
            "name_offset": name_offset,
            "flags": flags,
            "attribute_id": attribute_id,
            "offset": offset
        })

        # Move to next attribute
        offset += attribute_length

    return attributes
