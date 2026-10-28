"""$I30 directory indexes: live entries and deleted ("ghost") entries.

A directory lists its children in a B-tree of INDEX_ENTRY structures:
the root node lives in $INDEX_ROOT (resident), larger directories add
4 KiB "INDX" pages in $INDEX_ALLOCATION. Each entry's key is a copy of
the child's $FILE_NAME (name, parent, four timestamps, sizes).

When a file is deleted its entry is removed and later entries shift
down, but the old bytes often stay in the node's slack space (between
the "used" and "allocated" ends of the node) or in INDX pages that the
index $BITMAP marks as unused. Those leftovers are ghost entries: proof
that a name existed in this directory, often with its timestamps.

Reference: forensicx core/ntfs/IndexRecord.ts. Unlike that version,
slack is scanned explicitly (its walker stops at the end-of-node entry,
which is exactly where slack begins).
"""
import struct
from dataclasses import dataclass

from fixup import apply_fixup

from engine.metafiles.common import (
    ATTR_BITMAP,
    ATTR_INDEX_ALLOCATION,
    ATTR_INDEX_ROOT,
    FILE_NAME_HEADER_SIZE,
    decode_file_name,
    mft_reference,
    scan_file_names,
)
from engine.metafiles.record import read_record_attributes
from engine.metafiles.stream import AttributeStream

INDX_SIGNATURE = b"INDX"
INDEX_ENTRY_HEADER = 0x10
ENTRY_FLAG_LAST = 0x02

# Do not read absurd $INDEX_ALLOCATION streams from corrupt records.
MAX_INDEX_ALLOCATION = 256 * 1024 * 1024


@dataclass(frozen=True)
class IndexEntry:
    directory_record: int
    file_record: int
    file_sequence: int
    key: object  # FileNameKey
    # "root", "allocation", "slack" or "unused-block"
    location: str

    @property
    def is_ghost(self):
        return self.location in ("slack", "unused-block")


@dataclass
class DirectoryIndex:
    directory_record: int
    live: list
    ghosts: list


def _walk_live(buffer, node_header, directory_record, location):
    """Live entries of one node, plus the byte range of its slack."""
    entries_offset, used, allocated = struct.unpack_from("<III", buffer, node_header)
    start = node_header + entries_offset
    used_end = min(node_header + used, len(buffer))
    allocated_end = min(node_header + allocated, len(buffer))

    entries = []
    position = start
    while position + INDEX_ENTRY_HEADER <= used_end:
        reference, length, key_length, flags = struct.unpack_from(
            "<QHHH", buffer, position
        )
        if flags & ENTRY_FLAG_LAST or length < INDEX_ENTRY_HEADER:
            break
        if position + length > used_end:
            break
        if key_length >= FILE_NAME_HEADER_SIZE:
            key = decode_file_name(buffer, position + INDEX_ENTRY_HEADER)
            if key is not None:
                record, sequence = mft_reference(reference)
                entries.append(IndexEntry(
                    directory_record, record, sequence, key, location
                ))
        position += length

    return entries, (max(used_end, start), allocated_end)


def _carve(buffer, start, end, directory_record, location):
    """Plausible $FILE_NAME keys in a slack range that name this directory."""
    entries = []
    for offset, key in scan_file_names(buffer, start, end):
        if key.parent_record != directory_record:
            continue
        header = offset - INDEX_ENTRY_HEADER
        record, sequence = (0, 0)
        if header >= 0:
            record, sequence = mft_reference(
                struct.unpack_from("<Q", buffer, header)[0]
            )
        entries.append(IndexEntry(
            directory_record, record, sequence, key, location
        ))
    return entries


def _parse_node(buffer, node_header, directory_record, location, scan_slack):
    live, (slack_start, slack_end) = _walk_live(
        buffer, node_header, directory_record, location
    )
    ghosts = []
    if scan_slack and slack_end > slack_start:
        ghosts = _carve(buffer, slack_start, slack_end, directory_record, "slack")
    return live, ghosts


def _block_in_use(bitmap, block_index):
    if bitmap is None:
        return True
    byte = block_index // 8
    return byte < len(bitmap) and bool(bitmap[byte] & (1 << (block_index % 8)))


def read_directory_index(parser, directory_record, scan_slack=True):
    """Parse a directory's $I30 index into live and ghost entries."""
    record = read_record_attributes(parser, directory_record)

    live, ghosts = [], []

    root = record.find(ATTR_INDEX_ROOT, "$I30")
    block_size = None
    if root is not None and root.resident and len(root.content) >= 0x20:
        block_size = struct.unpack_from("<I", root.content, 0x08)[0]
        node_live, node_ghosts = _parse_node(
            root.content, 0x10, directory_record, "root", scan_slack
        )
        live += node_live
        ghosts += node_ghosts

    allocation = record.find(ATTR_INDEX_ALLOCATION, "$I30")
    if allocation is not None and not allocation.resident:
        if not block_size or block_size & (block_size - 1):
            block_size = parser.index_block_size

        bitmap_attribute = record.find(ATTR_BITMAP, "$I30")
        bitmap = None
        if bitmap_attribute is not None:
            bitmap = (
                bitmap_attribute.content if bitmap_attribute.resident
                else AttributeStream(
                    parser.image, parser.geometry, bitmap_attribute
                ).read_all()
            )

        data = AttributeStream(parser.image, parser.geometry, allocation).read_all(
            MAX_INDEX_ALLOCATION
        )

        for block_index, offset in enumerate(range(0, len(data) - block_size + 1, block_size)):
            page = data[offset:offset + block_size]
            if page[:4] != INDX_SIGNATURE:
                continue
            try:
                page = apply_fixup(page)
            except ValueError:
                continue
            if _block_in_use(bitmap, block_index):
                node_live, node_ghosts = _parse_node(
                    page, 0x18, directory_record, "allocation", scan_slack
                )
                live += node_live
                ghosts += node_ghosts
            elif scan_slack:
                # A whole node the B-tree no longer uses: everything in it
                # is left over from earlier states of the directory.
                ghosts += _carve(page, 0x18, len(page), directory_record, "unused-block")

    return DirectoryIndex(directory_record, live, _dedupe_ghosts(live, ghosts))


def _dedupe_ghosts(live, ghosts):
    """Drop ghosts that are still listed live, and repeated copies."""
    live_names = {(entry.key.name.lower(), entry.key.parent_record) for entry in live}
    seen = set()
    unique = []
    for entry in ghosts:
        identity = (entry.key.name.lower(), entry.key.parent_record)
        if identity in live_names:
            continue
        signature = identity + (entry.key.created, entry.key.modified)
        if signature in seen:
            continue
        seen.add(signature)
        unique.append(entry)
    return unique


def find_child(parser, directory_record, name):
    """Record number of a live child called ``name`` (case-insensitive)."""
    wanted = name.lower()
    for entry in read_directory_index(parser, directory_record, scan_slack=False).live:
        if entry.key.name.lower() == wanted:
            return entry.file_record
    return None
