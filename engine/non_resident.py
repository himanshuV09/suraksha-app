import struct

def parse_non_resident_attribute(record, attribute):

    offset = attribute["offset"]

    starting_vcn = struct.unpack("<Q", record[offset + 16:offset + 24])[0]

    last_vcn = struct.unpack("<Q", record[offset + 24:offset + 32])[0]

    data_run_offset = struct.unpack("<H", record[offset + 32:offset + 34])[0]

    compression_unit = struct.unpack("<H", record[offset + 34:offset + 36])[0]

    allocated_size = struct.unpack("<Q", record[offset + 40:offset + 48])[0]

    real_size = struct.unpack("<Q", record[offset + 48:offset + 56])[0]

    initialized_size = struct.unpack("<Q", record[offset + 56:offset + 64])[0]

    runs_start = offset + data_run_offset


    return {

        "starting_vcn": starting_vcn,
        "last_vcn": last_vcn,
        "cluster_count": last_vcn - starting_vcn + 1,
        "data_run_offset": data_run_offset,
        "compression_unit": compression_unit,
        "allocated_size": allocated_size,
        "real_size": real_size,
        "initialized_size": initialized_size,
        "runs_start": runs_start
    }

class DataRunParseError(ValueError):
    """A non-resident attribute's data-run list is structurally invalid."""


def parse_data_runs(record, runs_offset, end_offset=None):
    """Decode a non-resident attribute's data-run list.

    Args:
        record: the record bytes.
        runs_offset: offset of the first run header.
        end_offset: end of the owning attribute; runs must not cross it.
            Defaults to the end of the record.

    Raises:
        DataRunParseError: the list is malformed (no end marker, invalid
            header, or a negative cluster number).
    """

    limit = len(record) if end_offset is None else min(end_offset, len(record))

    runs = []

    offset = runs_offset

    previous_lcn = 0

    run_number = 0

    while True:

        if offset >= limit:
            raise DataRunParseError(
                "Data-run list has no end marker before the end of "
                "its attribute"
            )

        header = record[offset]

        # End marker
        if header == 0:
            break

        length_size = header & 0x0F

        offset_size = (header >> 4) & 0x0F

        if length_size == 0 or length_size > 8 or offset_size > 8:
            raise DataRunParseError(
                f"Invalid data-run header 0x{header:02x} at offset {offset}"
            )

        if offset + 1 + length_size + offset_size > limit:
            raise DataRunParseError(
                f"Data run at offset {offset} extends past its attribute"
            )

        offset += 1

        run_number += 1

        run_length = int.from_bytes(
            record[offset:offset + length_size],
            byteorder="little"
        )

        offset += length_size

        run_offset_bytes = record[
            offset:offset + offset_size
        ]

        run_offset = int.from_bytes(
            run_offset_bytes,
            byteorder="little",
            signed=True
        )


        offset += offset_size

        if offset_size == 0:
            current_lcn = None
            is_sparse = True
        else:
            current_lcn = previous_lcn + run_offset
            is_sparse = False

            if current_lcn < 0:
                raise DataRunParseError(
                    f"Data run {run_number} points to negative cluster "
                    f"{current_lcn}"
                )

        runs.append({
            
            "run_number": run_number,
            "length": run_length,
            "lcn": current_lcn,
            "sparse": is_sparse,
        })

        if not is_sparse:
            previous_lcn = current_lcn

    return runs

