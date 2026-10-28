import struct

import pytest

from attributes import AttributeParseError, parse_attributes
from non_resident import DataRunParseError, parse_data_runs


def _attribute(type_code, length):
    header = bytearray(16)
    struct.pack_into("<II", header, 0, type_code, length)
    return bytes(header) + bytes(max(0, length - 16))


END = struct.pack("<I", 0xFFFFFFFF)


def test_parses_a_well_formed_attribute_list():
    record = _attribute(0x10, 24) + _attribute(0x30, 32) + END

    attributes = parse_attributes(record, 0)

    assert [a["type"] for a in attributes] == ["$STANDARD_INFORMATION", "$FILE_NAME"]


def test_zero_length_attribute_raises_instead_of_looping_forever():
    record = _attribute(0x10, 24) + struct.pack("<II", 0x30, 0) + bytes(64) + END

    with pytest.raises(AttributeParseError, match="invalid length 0"):
        parse_attributes(record, 0)


def test_attribute_running_past_the_record_is_rejected():
    record = _attribute(0x10, 24) + struct.pack("<II", 0x30, 4096) + bytes(8)

    with pytest.raises(AttributeParseError, match="past the end"):
        parse_attributes(record, 0)


def test_missing_end_marker_is_rejected():
    with pytest.raises(AttributeParseError, match="no end marker"):
        parse_attributes(_attribute(0x10, 24), 0)


def test_data_runs_decode_normally():
    # 0x21: 1-byte length, 2-byte offset. 8 clusters at LCN 0x1234.
    runs = parse_data_runs(bytes([0x21, 0x08, 0x34, 0x12, 0x00]), 0)

    assert runs == [{"run_number": 1, "length": 8, "lcn": 0x1234, "sparse": False}]


def test_data_runs_without_terminator_are_rejected():
    with pytest.raises(DataRunParseError, match="no end marker"):
        parse_data_runs(bytes([0x21, 0x08, 0x34, 0x12]), 0)


def test_data_runs_may_not_cross_their_attribute():
    record = bytes([0x21, 0x08, 0x34, 0x12, 0x00])

    with pytest.raises(DataRunParseError):
        parse_data_runs(record, 0, end_offset=3)


def test_data_run_pointing_to_negative_cluster_is_rejected():
    # Offset -1 relative to LCN 0.
    with pytest.raises(DataRunParseError, match="negative cluster"):
        parse_data_runs(bytes([0x11, 0x01, 0xFF, 0x00]), 0)
