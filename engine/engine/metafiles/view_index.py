"""NTFS view indexes: $ObjId:$O, $Quota:$O/$Q, $Reparse:$R, $Secure:$SII/$SDH.

These are B-trees like directory indexes ($I30), but their entries hold
an arbitrary key and an optional data part instead of a $FILE_NAME:

    0x00 data offset  u16      0x08 entry length u16
    0x02 data length  u16      0x0A key length   u16
    0x04 reserved     u32      0x0C flags        u16   (0x02 = last entry)
    0x10 key ...               (data at entry + data offset)

The root node is in $INDEX_ROOT:<name>, further nodes are INDX pages in
$INDEX_ALLOCATION:<name>; the $BITMAP:<name> attribute says which pages
are in use.
"""
import struct

from fixup import apply_fixup

from engine.metafiles.common import ATTR_BITMAP, ATTR_INDEX_ALLOCATION, ATTR_INDEX_ROOT
from engine.metafiles.record import read_record_attributes
from engine.metafiles.stream import AttributeStream

ENTRY_FLAG_LAST = 0x02
MAX_INDEX_ALLOCATION = 64 * 1024 * 1024


def _walk(buffer, node_header):
    entries_offset, used, _ = struct.unpack_from("<III", buffer, node_header)
    position = node_header + entries_offset
    end = min(node_header + used, len(buffer))
    entries = []
    while position + 0x10 <= end:
        data_offset, data_length, _, length, key_length, flags = struct.unpack_from(
            "<HHIHHH", buffer, position
        )
        if flags & ENTRY_FLAG_LAST or length < 0x10 or position + length > end:
            break
        key = bytes(buffer[position + 0x10:position + 0x10 + key_length])
        data = b""
        if data_length and data_offset + data_length <= length:
            data = bytes(buffer[position + data_offset:position + data_offset + data_length])
        entries.append((key, data))
        position += length
    return entries


def read_view_index(parser, record_number, name, record=None):
    """All live (key, data) pairs of index ``name`` in a record."""
    record = record or read_record_attributes(parser, record_number)
    entries = []

    root = record.find(ATTR_INDEX_ROOT, name)
    block_size = parser.index_block_size
    if root is not None and root.resident and len(root.content) >= 0x20:
        block_size = struct.unpack_from("<I", root.content, 0x08)[0] or block_size
        entries += _walk(root.content, 0x10)

    allocation = record.find(ATTR_INDEX_ALLOCATION, name)
    if allocation is None or allocation.resident:
        return entries

    bitmap_attribute = record.find(ATTR_BITMAP, name)
    bitmap = None
    if bitmap_attribute is not None:
        bitmap = (
            bitmap_attribute.content if bitmap_attribute.resident
            else AttributeStream(parser.image, parser.geometry, bitmap_attribute).read_all()
        )

    data = AttributeStream(parser.image, parser.geometry, allocation).read_all(
        MAX_INDEX_ALLOCATION
    )
    for block, offset in enumerate(range(0, len(data) - block_size + 1, block_size)):
        if bitmap is not None:
            byte = block // 8
            if byte >= len(bitmap) or not bitmap[byte] & (1 << (block % 8)):
                continue
        page = data[offset:offset + block_size]
        if page[:4] != b"INDX":
            continue
        try:
            entries += _walk(apply_fixup(page), 0x18)
        except ValueError:
            continue
    return entries
