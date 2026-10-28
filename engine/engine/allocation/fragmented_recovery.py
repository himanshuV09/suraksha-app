"""Recover files whose data continues after an allocated block.

Only formats with an internal integrity check are reassembled: a PNG's
chunk CRC-32s, a ZIP's central directory (which must point back at every
local header), a GZIP's CRC-32 of the decompressed data, a PDF's
startxref. A wrong reassembly practically cannot pass those checks.
JPEG has no checksum, so a wrongly joined JPEG could still look valid;
it is deliberately excluded.
"""
import hashlib
import struct
from bisect import bisect_right

from engine.allocation.format_validators import BoundedReader, FormatError, VALIDATORS
from engine.allocation.free_space_stream import FreeSpaceStream

FRAGMENT_CAPABLE = {"PNG", "ZIP", "GZIP", "PDF"}

# Reassembly reads at most this much free space per candidate.
MAX_REASSEMBLY_SIZE = 16 * 1024 * 1024

# Reassembled files are less certain than contiguous ones.
FRAGMENTED_CONFIDENCE = 0.4


class _Covered:
    """Byte ranges of files already recovered, for "is this inside one?"."""

    def __init__(self, extents):
        merged = []
        for start, end in sorted(extents):
            if merged and start <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], end)
            else:
                merged.append([start, end])
        self.ranges = merged
        self.starts = [start for start, _ in merged]

    def contains(self, offset):
        index = bisect_right(self.starts, offset) - 1
        return index >= 0 and offset < self.ranges[index][1]

    def add(self, start, end):
        self.__init__([*map(tuple, self.ranges), (start, end)])


def reassemble(image, regions, candidate, contiguous_bytes, max_size=MAX_REASSEMBLY_SIZE):
    """Try to validate ``candidate`` across free regions.

    Returns (data, size, reason, extension, fragments), or None when the
    candidate is not fragmented or does not validate.
    """
    if candidate.signature not in FRAGMENT_CAPABLE:
        return None
    try:
        stream = FreeSpaceStream(image, regions, candidate.offset, candidate)
    except LookupError:
        return None
    if stream.remaining_bytes <= contiguous_bytes:
        return None  # no more free space after this region

    reader = BoundedReader(stream, min(stream.remaining_bytes, max_size))
    try:
        size, reason, *rest = VALIDATORS[candidate.signature](reader)
    except (FormatError, struct.error, ValueError):
        return None
    if size <= contiguous_bytes:
        return None  # fits in one region: not a fragmented file

    fragments = stream.fragments(size)
    data = stream.read(size, 0)
    if len(data) != size:
        return None
    reason = f"{reason} (reassembled from {len(fragments)} free-space fragments)"
    return data, size, reason, (rest[0] if rest else candidate.extension), fragments


def recover_fragmented(image, regions, candidates, validated, context_factory,
                       repository, case_id, source_image, cluster_size,
                       volume_offset, existing_offsets):
    """Second pass over candidates that failed contiguous validation.

    Returns (persisted list, retried count).
    """
    covered = _Covered(
        (item.offset, item.offset + item.detected_size) for item in validated
    )
    validated_offsets = {item.offset for item in validated}
    persisted = []
    retried = 0

    for candidate in sorted(candidates, key=lambda item: item.offset):
        if (
            candidate.signature not in FRAGMENT_CAPABLE
            or candidate.offset in validated_offsets
            or candidate.offset in existing_offsets
            or covered.contains(candidate.offset)
        ):
            continue
        try:
            context = context_factory.create(candidate)
        except LookupError:
            continue
        if context.remaining_bytes >= MAX_REASSEMBLY_SIZE:
            continue  # contiguous validation already had room enough

        retried += 1
        outcome = reassemble(image, regions, candidate, context.remaining_bytes)
        if outcome is None:
            continue

        data, size, reason, extension, fragments = outcome
        sha256 = hashlib.sha256(data).hexdigest()
        artifact_id = repository.create_fragmented(
            case_id,
            signature=candidate.signature,
            extension=extension,
            size=size,
            sha256=sha256,
            confidence=FRAGMENTED_CONFIDENCE,
            source_image=source_image,
            region=context.region,
            fragments=fragments,
            cluster_size=cluster_size,
            volume_offset=volume_offset,
            validation_reason=reason,
        )
        covered.add(candidate.offset, candidate.offset + size)
        existing_offsets.add(candidate.offset)
        persisted.append({
            "artifact_id": artifact_id,
            "signature": candidate.signature,
            "extension": extension,
            "size": size,
            "sha256": sha256,
            "source_offset": candidate.offset,
            "fragments": len(fragments),
        })

    return persisted, retried
