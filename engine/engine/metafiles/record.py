"""Read every attribute of one MFT record, following $ATTRIBUTE_LIST.

The evidence pipeline keeps only the handful of attribute fields it
needs. Metafile parsing needs the rest: named streams ($UsnJrnl:$J,
$BadClus:$Bad), volume attributes, index attributes, and the pieces of
large attributes that live in extension records.
"""
import struct
from dataclasses import dataclass, field

from attributes import ATTRIBUTE_TYPES, parse_attributes
from fixup import apply_fixup
from mft import parse_mft_header
from non_resident import parse_data_runs, parse_non_resident_attribute
from resident import parse_resident_attribute

from engine.metafiles.common import ATTR_ATTRIBUTE_LIST, mft_reference
from engine.metafiles.stream import AttributeStream

# A corrupt $ATTRIBUTE_LIST must not send us around the MFT forever.
MAX_EXTENSION_RECORDS = 256


@dataclass
class Attribute:
    type_code: int
    name: str
    resident: bool
    attribute_id: int
    flags: int
    # Resident attributes.
    content: bytes | None = None
    # Non-resident attributes.
    runs: list = field(default_factory=list)
    starting_vcn: int = 0
    last_vcn: int = -1
    real_size: int = 0
    allocated_size: int = 0
    initialized_size: int = 0
    # Which record this piece came from (differs for extension records).
    record_number: int = 0

    @property
    def type_name(self):
        return ATTRIBUTE_TYPES.get(self.type_code, hex(self.type_code))

    @property
    def size(self):
        return len(self.content or b"") if self.resident else self.real_size

    @property
    def is_compressed(self):
        return bool(self.flags & 0x0001)

    @property
    def is_encrypted(self):
        return bool(self.flags & 0x4000)

    @property
    def is_sparse(self):
        return bool(self.flags & 0x8000)

    @property
    def fragment_count(self):
        return sum(1 for run in self.runs if not run["sparse"])


@dataclass
class RecordAttributes:
    record_number: int
    sequence_number: int
    in_use: bool
    directory: bool
    base_record: int
    attributes: list
    extension_records: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    def find(self, type_code, name=""):
        for attribute in self.attributes:
            if attribute.type_code == type_code and attribute.name == name:
                return attribute
        return None

    def find_all(self, type_code):
        return [a for a in self.attributes if a.type_code == type_code]

    def streams(self):
        """All $DATA streams: [{"name", "size", "resident"}]."""
        return [
            {
                "name": attribute.name,
                "size": attribute.size,
                "resident": attribute.resident,
            }
            for attribute in self.find_all(0x80)
        ]


def _parse_record(raw, record_number):
    record = apply_fixup(raw)
    header = parse_mft_header(record)

    if header["signature"] != "FILE":
        raise ValueError(f"MFT record {record_number} has no FILE signature")

    base_reference = struct.unpack_from("<Q", record, 32)[0]
    base_record, _ = mft_reference(base_reference)

    attributes = []
    for item in parse_attributes(record, header["first_attribute_offset"]):
        type_code = int(item["type_code"], 16)
        common = dict(
            type_code=type_code,
            name=item["stream_name"],
            attribute_id=item["attribute_id"],
            flags=item["flags"],
            record_number=record_number,
        )

        if item["resident"] == 0:
            resident = parse_resident_attribute(record, item)
            attributes.append(
                Attribute(resident=True, content=resident["content"], **common)
            )
            continue

        info = parse_non_resident_attribute(record, item)
        runs = parse_data_runs(
            record, info["runs_start"], item["offset"] + item["length"]
        )
        attributes.append(Attribute(
            resident=False,
            runs=runs,
            starting_vcn=info["starting_vcn"],
            last_vcn=info["last_vcn"],
            real_size=info["real_size"],
            allocated_size=info["allocated_size"],
            initialized_size=info["initialized_size"],
            **common,
        ))

    return header, base_record, attributes


def read_record_attributes(parser, record_number):
    """Parse one MFT record (with extension records) into Attributes.

    Raises ValueError if the base record is unreadable.
    """
    raw = parser.read_record(record_number)
    if not raw or len(raw) < 48:
        raise ValueError(f"MFT record {record_number} could not be read")

    header, base_record, attributes = _parse_record(raw, record_number)
    result = RecordAttributes(
        record_number=record_number,
        sequence_number=header["sequence_number"],
        in_use=bool(header["flags"] & 0x01),
        directory=bool(header["flags"] & 0x02),
        base_record=base_record,
        attributes=attributes,
    )

    attribute_list = result.find(ATTR_ATTRIBUTE_LIST)
    if attribute_list is not None:
        _merge_extension_records(parser, result, attribute_list)

    return result


def _attribute_list_entries(parser, attribute_list):
    if attribute_list.resident:
        data = attribute_list.content or b""
    else:
        data = AttributeStream(
            parser.image, parser.geometry, attribute_list
        ).read_all()

    entries = []
    offset = 0
    while offset + 0x1A <= len(data):
        type_code, length, name_length, name_offset = struct.unpack_from(
            "<IHBB", data, offset
        )
        if length < 0x1A or offset + length > len(data):
            break
        starting_vcn, reference = struct.unpack_from("<QQ", data, offset + 8)
        name = bytes(
            data[offset + name_offset:offset + name_offset + 2 * name_length]
        ).decode("utf-16le", errors="replace")
        record, _ = mft_reference(reference)
        entries.append((type_code, name, starting_vcn, record))
        offset += length
    return entries


def _merge_extension_records(parser, result, attribute_list):
    """Pull attribute pieces from extension records into the base record.

    Non-resident attributes split across records are joined into one
    Attribute whose runs cover the whole stream, ordered by VCN.
    """
    try:
        entries = _attribute_list_entries(parser, attribute_list)
    except Exception as error:
        result.warnings.append(f"Unreadable $ATTRIBUTE_LIST: {error}")
        return

    extension_records = sorted({
        record for _, _, _, record in entries
        if record != result.record_number
    })[:MAX_EXTENSION_RECORDS]

    pieces = {}
    for attribute in result.attributes:
        pieces.setdefault((attribute.type_code, attribute.name), []).append(attribute)

    for record_number in extension_records:
        try:
            _, base, attributes = _parse_record(
                parser.read_record(record_number), record_number
            )
        except Exception as error:
            result.warnings.append(
                f"Extension record {record_number} unreadable: {error}"
            )
            continue
        if base != result.record_number:
            result.warnings.append(
                f"Extension record {record_number} belongs to record {base}"
            )
            continue
        result.extension_records.append(record_number)
        for attribute in attributes:
            pieces.setdefault((attribute.type_code, attribute.name), []).append(attribute)

    merged = []
    for group in pieces.values():
        if len(group) == 1 or group[0].resident:
            merged.extend(group)
            continue
        group.sort(key=lambda piece: piece.starting_vcn)
        first = group[0]  # sizes are only valid in the VCN-0 piece
        first.runs = [run for piece in group for run in piece.runs]
        first.last_vcn = max(piece.last_vcn for piece in group)
        merged.append(first)

    result.attributes = merged
