"""Build small, synthetic NTFS disk images for tests.

The images contain just enough real NTFS structure for the engine to
parse them end to end: a boot sector, an $MFT (optionally fragmented),
a root directory, $Bitmap, and any user files the test asks for. They
can also be wrapped in an MBR partition table, and can contain
deliberately malformed MFT records.

Everything is written byte-for-byte as NTFS lays it out on disk, so the
production parser is exercised exactly as it would be on a real image.
"""
import math
import struct
from dataclasses import dataclass, field

SECTOR_SIZE = 512

# 2024-01-01 00:00:00 UTC as a Windows FILETIME.
DEFAULT_FILETIME = 133485408000000000

ROOT_RECORD = 5
BITMAP_RECORD = 6

ATTR_STANDARD_INFORMATION = 0x10
ATTR_FILE_NAME = 0x30
ATTR_DATA = 0x80
END_MARKER = 0xFFFFFFFF

FLAG_IN_USE = 0x01
FLAG_DIRECTORY = 0x02


@dataclass
class FileSpec:
    """One MFT record to place in the image.

    For a resident file, leave ``runs`` empty and put the bytes in
    ``data``. For a non-resident file, give ``runs`` as a list of
    ``(lcn, cluster_count)`` pairs; use ``lcn=None`` for a sparse run.
    ``data`` is then written across those clusters.

    ``malformed`` writes an attribute whose length field is zero, the
    kind of corruption that used to hang the parser.

    ``extra_attributes`` adds further attributes (``RawAttribute``), such
    as $VOLUME_NAME, an $INDEX_ROOT or a named stream like $UsnJrnl:$J.
    A spec with a system record number (e.g. 5) replaces the default one.
    """

    record_number: int
    name: str
    data: bytes = b""
    runs: list = field(default_factory=list)
    parent: int = ROOT_RECORD
    parent_sequence: int = ROOT_RECORD
    sequence: int = 1
    directory: bool = False
    deleted: bool = False
    malformed: bool = False
    extra_attributes: list = field(default_factory=list)
    # FILETIME for all four timestamps (None: DEFAULT_FILETIME).
    filetime: int | None = None
    # Bytes left after the record's used area (old data, as NTFS leaves it).
    record_slack: bytes = b""


@dataclass
class RawAttribute:
    """An extra attribute: resident ``content``, or non-resident ``runs``.

    For non-resident attributes the bytes are placed in the clusters with
    NtfsImageBuilder.add_cluster_data(); ``real_size`` is the stream size.
    """

    type_code: int
    content: bytes | None = None
    name: str = ""
    runs: list | None = None
    real_size: int = 0


@dataclass
class BuiltImage:
    """What the builder produced, for assertions in tests."""

    path: str
    volume_offset: int
    cluster_size: int
    total_clusters: int
    record_size: int
    mft_runs: list
    allocated_clusters: set
    payload_offsets: dict  # name -> absolute image offset


class NtfsImageBuilder:

    def __init__(
        self,
        *,
        cluster_size=4096,
        total_clusters=256,
        record_size=1024,
        mft_runs=((4, 8),),
        bitmap_lcn=2,
        partition_offset=0,
    ):
        if cluster_size % SECTOR_SIZE:
            raise ValueError("cluster_size must be a multiple of 512")
        if partition_offset % SECTOR_SIZE:
            raise ValueError("partition_offset must be sector aligned")

        self.cluster_size = cluster_size
        self.total_clusters = total_clusters
        self.record_size = record_size
        self.mft_runs = [tuple(run) for run in mft_runs]
        self.bitmap_lcn = bitmap_lcn
        self.partition_offset = partition_offset

        self.files = []
        self.unallocated_payloads = []  # (name, lcn, bytes)
        self.cluster_data = []  # (lcn, bytes), allocated

        mft_bytes = sum(length for _, length in self.mft_runs) * cluster_size
        self.mft_record_slots = mft_bytes // record_size

    # -----------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------

    def add_file(self, spec):
        if not 0 <= spec.record_number < self.mft_record_slots:
            raise ValueError(
                f"record {spec.record_number} does not fit in the $MFT "
                f"({self.mft_record_slots} slots)"
            )
        self.files.append(spec)
        return self

    def add_cluster_data(self, lcn, data):
        """Write bytes into clusters that $Bitmap marks as allocated."""
        self.cluster_data.append((lcn, data))
        return self

    def add_unallocated_payload(self, name, lcn, data):
        """Write bytes into clusters that $Bitmap marks as free."""
        self.unallocated_payloads.append((name, lcn, data))
        return self

    def build(self, path):
        volume = bytearray(self.total_clusters * self.cluster_size)
        allocated = {0}  # boot sector cluster

        for lcn, length in self.mft_runs:
            allocated.update(range(lcn, lcn + length))

        bitmap_size = math.ceil(self.total_clusters / 8)
        bitmap_clusters = math.ceil(bitmap_size / self.cluster_size)
        allocated.update(
            range(self.bitmap_lcn, self.bitmap_lcn + bitmap_clusters)
        )

        for spec in self.files:
            if spec.deleted:
                continue  # NTFS frees a deleted file's clusters in $Bitmap
            runs = list(spec.runs)
            for attribute in spec.extra_attributes:
                runs += attribute.runs or []
            for lcn, length in runs:
                if lcn is not None:
                    allocated.update(range(lcn, lcn + length))

        for lcn, data in self.cluster_data:
            allocated.update(range(lcn, lcn + math.ceil(len(data) / self.cluster_size)))
            start = lcn * self.cluster_size
            volume[start:start + len(data)] = data

        # User specs replace system records with the same number.
        overridden = {spec.record_number for spec in self.files}
        records = [
            spec for spec in self._system_records(bitmap_size, bitmap_clusters)
            if spec.record_number not in overridden
        ]
        records += self.files

        # $MFT:$BITMAP: one bit per MFT record, set for records in use.
        mft_bitmap = bytearray(_align(math.ceil(self.mft_record_slots / 8), 8))
        for spec in records:
            if not spec.deleted:
                mft_bitmap[spec.record_number // 8] |= 1 << (spec.record_number % 8)
        for spec in records:
            if spec.record_number == 0:
                spec.extra_attributes = list(spec.extra_attributes) + [
                    RawAttribute(0xB0, bytes(mft_bitmap))
                ]

        # File contents.
        for spec in self.files:
            if spec.runs:
                self._write_runs(volume, spec.runs, spec.data)

        # Free-space payloads (must not collide with allocated clusters).
        payload_offsets = {}
        for name, lcn, data in self.unallocated_payloads:
            clusters = range(lcn, lcn + math.ceil(len(data) / self.cluster_size))
            if allocated.intersection(clusters):
                raise ValueError(f"payload {name!r} overlaps allocated space")
            start = lcn * self.cluster_size
            volume[start:start + len(data)] = data
            payload_offsets[name] = self.partition_offset + start

        # $Bitmap contents.
        bitmap = bytearray(bitmap_clusters * self.cluster_size)
        for cluster in allocated:
            bitmap[cluster // 8] |= 1 << (cluster % 8)
        start = self.bitmap_lcn * self.cluster_size
        volume[start:start + len(bitmap)] = bitmap

        # MFT records, placed through the $MFT data runs.
        built = {}
        for spec in records:
            built[spec.record_number] = self._record(spec)
            self._place_record(volume, spec.record_number, built[spec.record_number])

        # $MFTMirr (record 1) with runs: store copies of the first records.
        mirror = next((s for s in records if s.record_number == 1 and s.runs), None)
        if mirror is not None:
            count = sum(n for _, n in mirror.runs) * self.cluster_size // self.record_size
            copies = b"".join(
                built.get(number, bytes(self.record_size)) for number in range(count)
            )
            self._write_runs(volume, mirror.runs, copies)

        volume[0:SECTOR_SIZE] = self._boot_sector()

        image = bytearray()
        if self.partition_offset:
            image += self._mbr(len(volume))
            image += bytes(self.partition_offset - len(image))
        image += volume

        with open(path, "wb") as handle:
            handle.write(image)

        return BuiltImage(
            path=str(path),
            volume_offset=self.partition_offset,
            cluster_size=self.cluster_size,
            total_clusters=self.total_clusters,
            record_size=self.record_size,
            mft_runs=list(self.mft_runs),
            allocated_clusters=allocated,
            payload_offsets=payload_offsets,
        )

    # -----------------------------------------------------------------
    # Volume layout
    # -----------------------------------------------------------------

    def _system_records(self, bitmap_size, bitmap_clusters):
        mft_size = self.mft_record_slots * self.record_size
        return [
            _SystemRecord(
                record_number=0,
                name="$MFT",
                runs=self.mft_runs,
                real_size=mft_size,
                sequence=1,
            ),
            FileSpec(
                record_number=ROOT_RECORD,
                name=".",
                sequence=ROOT_RECORD,
                directory=True,
            ),
            _SystemRecord(
                record_number=BITMAP_RECORD,
                name="$Bitmap",
                runs=[(self.bitmap_lcn, bitmap_clusters)],
                real_size=bitmap_size,
                sequence=BITMAP_RECORD,
            ),
        ]

    def _write_runs(self, volume, runs, data):
        position = 0
        for lcn, length in runs:
            size = length * self.cluster_size
            chunk = data[position:position + size]
            if lcn is not None:
                start = lcn * self.cluster_size
                volume[start:start + len(chunk)] = chunk
            position += size

    def _place_record(self, volume, record_number, record):
        """Write a record at its position in the (possibly split) $MFT."""
        stream_offset = record_number * self.record_size
        written = 0
        run_start = 0

        for lcn, length in self.mft_runs:
            run_end = run_start + length * self.cluster_size
            while written < len(record) and run_start <= stream_offset + written < run_end:
                position = stream_offset + written
                take = min(len(record) - written, run_end - position)
                volume_offset = lcn * self.cluster_size + (position - run_start)
                volume[volume_offset:volume_offset + take] = record[written:written + take]
                written += take
            run_start = run_end

        if written != len(record):
            raise ValueError(f"record {record_number} is outside the $MFT runs")

    def _boot_sector(self):
        sector = bytearray(SECTOR_SIZE)
        sector[0:3] = b"\xEB\x52\x90"
        sector[3:11] = b"NTFS    "
        struct.pack_into("<H", sector, 11, SECTOR_SIZE)
        sector[13] = self.cluster_size // SECTOR_SIZE
        sectors = self.total_clusters * self.cluster_size // SECTOR_SIZE
        struct.pack_into("<Q", sector, 40, sectors)
        struct.pack_into("<Q", sector, 48, self.mft_runs[0][0])
        struct.pack_into("<Q", sector, 56, self.mft_runs[0][0])
        # Record size as a negative power of two (e.g. -10 = 1024 bytes).
        struct.pack_into("<b", sector, 64, -int(math.log2(self.record_size)))
        struct.pack_into("<b", sector, 68, -12)  # 4 KiB index buffers
        struct.pack_into("<Q", sector, 72, 0x1234ABCD5678EF00)
        sector[510:512] = b"\x55\xAA"
        return sector

    def _mbr(self, volume_size):
        sector = bytearray(SECTOR_SIZE)
        entry = 446
        sector[entry + 4] = 0x07  # NTFS / exFAT partition type
        struct.pack_into("<I", sector, entry + 8, self.partition_offset // SECTOR_SIZE)
        struct.pack_into("<I", sector, entry + 12, volume_size // SECTOR_SIZE)
        sector[510:512] = b"\x55\xAA"
        return sector

    # -----------------------------------------------------------------
    # MFT records
    # -----------------------------------------------------------------

    def _record(self, spec):
        attributes = bytearray()
        attributes += _resident_attribute(
            ATTR_STANDARD_INFORMATION, _standard_information(spec.filetime), attribute_id=0
        )

        if spec.malformed:
            # Valid type, zero length: the parser must not loop forever.
            attributes += struct.pack("<II", ATTR_FILE_NAME, 0) + bytes(8)
        else:
            attributes += _resident_attribute(
                ATTR_FILE_NAME,
                _file_name(spec, self._data_size(spec), self._allocated_size(spec)),
                attribute_id=1,
            )

            if not spec.directory:
                if spec.runs:
                    attributes += _non_resident_attribute(
                        ATTR_DATA,
                        spec.runs,
                        real_size=self._data_size(spec),
                        allocated_size=self._allocated_size(spec),
                        attribute_id=2,
                    )
                else:
                    attributes += _resident_attribute(
                        ATTR_DATA, spec.data, attribute_id=2
                    )

            for number, extra in enumerate(spec.extra_attributes, start=3):
                if extra.runs:
                    attributes += _non_resident_attribute(
                        extra.type_code,
                        extra.runs,
                        real_size=extra.real_size,
                        allocated_size=sum(n for _, n in extra.runs) * self.cluster_size,
                        attribute_id=number,
                        name=extra.name,
                    )
                else:
                    attributes += _resident_attribute(
                        extra.type_code, extra.content or b"",
                        attribute_id=number, name=extra.name,
                    )

        attributes += struct.pack("<I", END_MARKER) + bytes(4)

        usa_count = self.record_size // SECTOR_SIZE + 1
        usa_offset = 48
        first_attribute = _align(usa_offset + 2 * usa_count, 8)
        used_size = first_attribute + len(attributes)

        if used_size > self.record_size:
            raise ValueError(f"record {spec.record_number} is too large")

        flags = 0 if spec.deleted else FLAG_IN_USE
        if spec.directory:
            flags |= FLAG_DIRECTORY

        record = bytearray(self.record_size)
        record[0:4] = b"FILE"
        struct.pack_into("<HH", record, 4, usa_offset, usa_count)
        struct.pack_into("<H", record, 16, spec.sequence)
        struct.pack_into("<H", record, 18, 1)
        struct.pack_into("<H", record, 20, first_attribute)
        struct.pack_into("<H", record, 22, flags)
        struct.pack_into("<I", record, 24, used_size)
        struct.pack_into("<I", record, 28, self.record_size)
        struct.pack_into("<H", record, 40, 3)
        struct.pack_into("<I", record, 44, spec.record_number)
        record[first_attribute:used_size] = attributes
        if spec.record_slack:
            slack_start = _align(used_size, 8)
            record[slack_start:slack_start + len(spec.record_slack)] = spec.record_slack

        return _apply_update_sequence(record, usa_offset, usa_count)

    def _data_size(self, spec):
        return getattr(spec, "real_size", None) or len(spec.data)

    def _allocated_size(self, spec):
        if spec.runs:
            return sum(length for _, length in spec.runs) * self.cluster_size
        return _align(len(spec.data), 8)


@dataclass
class _SystemRecord(FileSpec):
    """A metafile whose logical size is given explicitly."""

    real_size: int = 0


# ---------------------------------------------------------------------
# Attribute encoding
# ---------------------------------------------------------------------

def _align(value, boundary):
    return (value + boundary - 1) // boundary * boundary


def _name_fields(attribute, header_size, name):
    """Write an attribute name after the header; returns where data starts."""
    encoded = name.encode("utf-16le")
    attribute[9] = len(name)
    struct.pack_into("<H", attribute, 10, header_size if name else 0)
    attribute[header_size:header_size + len(encoded)] = encoded
    return _align(header_size + len(encoded), 8)


def _resident_attribute(type_code, content, attribute_id, name=""):
    header_size = 24
    content_offset = _align(header_size + 2 * len(name), 8)
    length = _align(content_offset + len(content), 8)
    attribute = bytearray(length)
    struct.pack_into("<II", attribute, 0, type_code, length)
    attribute[8] = 0  # resident
    _name_fields(attribute, header_size, name)
    struct.pack_into("<H", attribute, 14, attribute_id)
    struct.pack_into("<IH", attribute, 16, len(content), content_offset)
    attribute[content_offset:content_offset + len(content)] = content
    return attribute


def _non_resident_attribute(
    type_code, runs, real_size, allocated_size, attribute_id, name=""
):
    header_size = 64
    encoded_runs = encode_data_runs(runs)
    runs_offset = _align(header_size + 2 * len(name), 8)
    length = _align(runs_offset + len(encoded_runs), 8)
    total_clusters = sum(count for _, count in runs)

    attribute = bytearray(length)
    struct.pack_into("<II", attribute, 0, type_code, length)
    attribute[8] = 1  # non-resident
    _name_fields(attribute, header_size, name)
    struct.pack_into("<H", attribute, 14, attribute_id)
    struct.pack_into("<QQ", attribute, 16, 0, total_clusters - 1)
    struct.pack_into("<H", attribute, 32, runs_offset)
    struct.pack_into("<QQQ", attribute, 40, allocated_size, real_size, real_size)
    attribute[runs_offset:runs_offset + len(encoded_runs)] = encoded_runs
    return attribute


def _standard_information(filetime=None):
    content = bytearray(72)
    struct.pack_into("<QQQQ", content, 0, *([filetime or DEFAULT_FILETIME] * 4))
    return bytes(content)


def _file_name(spec, real_size, allocated_size):
    name = spec.name.encode("utf-16le")
    content = bytearray(66 + len(name))
    parent_reference = spec.parent | (spec.parent_sequence << 48)
    struct.pack_into("<Q", content, 0, parent_reference)
    struct.pack_into("<QQQQ", content, 8, *([spec.filetime or DEFAULT_FILETIME] * 4))
    struct.pack_into("<QQ", content, 40, allocated_size, real_size)
    struct.pack_into("<I", content, 56, 0x10000000 if spec.directory else 0x20)
    content[64] = len(spec.name)
    content[65] = 1  # Win32 namespace
    content[66:] = name
    return bytes(content)


def _minimal_signed_bytes(value):
    size = 1
    while not -(1 << (8 * size - 1)) <= value < (1 << (8 * size - 1)):
        size += 1
    return value.to_bytes(size, "little", signed=True)


def encode_data_runs(runs):
    """Encode ``(lcn or None, length)`` pairs as an NTFS data-run list."""
    encoded = bytearray()
    previous_lcn = 0

    for lcn, length in runs:
        length_bytes = length.to_bytes(
            max(1, (length.bit_length() + 7) // 8), "little"
        )
        if lcn is None:
            offset_bytes = b""
        else:
            offset_bytes = _minimal_signed_bytes(lcn - previous_lcn)
            previous_lcn = lcn

        encoded.append((len(offset_bytes) << 4) | len(length_bytes))
        encoded += length_bytes + offset_bytes

    encoded.append(0)
    return bytes(encoded)


def _apply_update_sequence(record, usa_offset, usa_count):
    """Protect each sector's last two bytes the way NTFS does on disk."""
    update_sequence_number = b"\x01\x00"
    record[usa_offset:usa_offset + 2] = update_sequence_number

    for index in range(1, usa_count):
        sector_end = index * SECTOR_SIZE - 2
        saved = usa_offset + index * 2
        record[saved:saved + 2] = record[sector_end:sector_end + 2]
        record[sector_end:sector_end + 2] = update_sequence_number

    return bytes(record)
