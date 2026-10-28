import struct

from dataclasses import dataclass, replace

from engine.allocation.format_validators import BoundedReader, FormatError, VALIDATORS

from engine.allocation.carving_models import SignatureCandidate
from engine.allocation.unallocated_candidate_context import (
    UnallocatedCandidateContext,
)
from engine.allocation.validated_candidate import ValidatedCandidate


@dataclass(frozen=True)
class ValidationResult:
    """Result of structurally validating a file-signature candidate."""

    valid: bool
    reason: str
    detected_size: int | None = None
    # A more specific extension found during validation (e.g. ZIP -> .docx).
    extension: str | None = None


class _JPEGParseError(Exception):
    """Expected malformed, truncated, or over-limit JPEG input."""


class _BoundedJPEGReader:
    """Chunk-cached reads limited to one candidate and its scan limit."""

    def __init__(self, context, limit, chunk_size):
        self.context = context
        self.limit = limit
        self.chunk_size = chunk_size
        self.cache_start = -1
        self.cache = b""

    def read(self, offset, size):
        if offset < 0 or size < 0 or offset + size > self.limit:
            raise _JPEGParseError("JPEG data is truncated or exceeds the validation limit")

        output = bytearray()
        position = offset
        end = offset + size

        while position < end:
            if not (
                self.cache_start <= position
                < self.cache_start + len(self.cache)
            ):
                self.cache_start = position
                amount = min(self.chunk_size, self.limit - position)
                try:
                    self.cache = self.context.read(
                        amount,
                        relative_offset=position,
                    )
                except (IOError, OSError, ValueError) as exc:
                    raise _JPEGParseError(
                        "Unable to read complete JPEG candidate data"
                    ) from exc

                if not self.cache:
                    raise _JPEGParseError("Unexpected end of JPEG data")

            cache_offset = position - self.cache_start
            amount = min(
                end - position,
                len(self.cache) - cache_offset,
            )

            if amount <= 0:
                raise _JPEGParseError("Unexpected end of JPEG data")

            output.extend(self.cache[cache_offset:cache_offset + amount])
            position += amount

        return bytes(output)

    def byte(self, offset):
        return self.read(offset, 1)[0]

    def uint16(self, offset):
        return int.from_bytes(self.read(offset, 2), "big")


class SignatureValidator:
    """Conservative, bounded structural validation for carving candidates."""

    # JPEG frame-header markers, excluding DHT, JPG, and DAC.
    SOF_MARKERS = {
        0xC0, 0xC1, 0xC2, 0xC3,
        0xC5, 0xC6, 0xC7,
        0xC9, 0xCA, 0xCB,
        0xCD, 0xCE, 0xCF,
    }

    STANDALONE_MARKERS = {0x01, *range(0xD0, 0xD8)}

    def __init__(
        self,
        max_candidate_size=64 * 1024 * 1024,
        read_chunk_size=1024 * 1024,
    ):
        if (
            not isinstance(max_candidate_size, int)
            or isinstance(max_candidate_size, bool)
        ):
            raise TypeError("max_candidate_size must be an integer")
        if max_candidate_size <= 0:
            raise ValueError("max_candidate_size must be positive")
        if (
            not isinstance(read_chunk_size, int)
            or isinstance(read_chunk_size, bool)
        ):
            raise TypeError("read_chunk_size must be an integer")
        if read_chunk_size <= 0:
            raise ValueError("read_chunk_size must be positive")

        self.max_candidate_size = max_candidate_size
        self.read_chunk_size = read_chunk_size

    def validate(self, context: UnallocatedCandidateContext) -> ValidationResult:
        if not isinstance(context, UnallocatedCandidateContext):
            raise TypeError("context must be an UnallocatedCandidateContext")

        candidate = context.candidate
        if not isinstance(candidate, SignatureCandidate):
            raise TypeError("context candidate must be a SignatureCandidate")

        if context.remaining_bytes <= 0:
            return ValidationResult(False, "No bytes remain after candidate")

        if candidate.signature == "JPEG":
            return self._validate_jpeg(context)

        if candidate.signature in VALIDATORS:
            return self._validate_format(context, VALIDATORS[candidate.signature])

        return ValidationResult(
            valid=False,
            reason=(
                "Signature-specific structural validation is not implemented "
                f"for {candidate.signature}"
            ),
        )

    def to_validated_candidate(
        self,
        context: UnallocatedCandidateContext,
    ) -> ValidatedCandidate | None:
        result = self.validate(context)

        if not result.valid:
            return None

        if result.detected_size is None:
            raise ValueError("Valid candidate is missing detected_size")

        candidate = context.candidate
        if result.extension and result.extension != candidate.extension:
            candidate = replace(candidate, extension=result.extension)

        return ValidatedCandidate(
            candidate=candidate,
            detected_size=result.detected_size,
            validation_reason=result.reason,
        )

    def _validate_format(self, context, validator):
        limit = min(context.remaining_bytes, self.max_candidate_size)
        reader = BoundedReader(context, limit, self.read_chunk_size)
        try:
            outcome = validator(reader)
        except (FormatError, struct.error) as exc:
            reason = str(exc)
            if context.remaining_bytes > self.max_candidate_size:
                reason += " (candidate validation limit reached)"
            return ValidationResult(False, reason)

        size, reason, *rest = outcome
        return ValidationResult(True, reason, detected_size=size,
                                extension=rest[0] if rest else None)

    def _validate_jpeg(self, context):
        limit = min(context.remaining_bytes, self.max_candidate_size)
        reader = _BoundedJPEGReader(
            context,
            limit,
            self.read_chunk_size,
        )

        try:
            return self._parse_jpeg(reader, limit)
        except _JPEGParseError as exc:
            reason = str(exc)
            if context.remaining_bytes > self.max_candidate_size:
                reason += " (candidate validation limit reached)"
            return ValidationResult(False, reason)

    def _parse_jpeg(self, reader, limit):
        if limit < 2 or reader.read(0, 2) != b"\xFF\xD8":
            return ValidationResult(
                False,
                "JPEG start signature mismatch",
            )

        position = 2
        saw_frame = False
        saw_scan = False
        component_count = 0
        in_scan = False

        while position < limit:
            if in_scan:
                marker = self._find_scan_marker(reader, position, limit)
                marker_offset, code, position = marker
                in_scan = False
            else:
                marker_offset = position

                if reader.byte(position) != 0xFF:
                    raise _JPEGParseError(
                        "Expected JPEG marker prefix outside scan data"
                    )

                while position < limit and reader.byte(position) == 0xFF:
                    position += 1

                if position >= limit:
                    raise _JPEGParseError(
                        "Truncated JPEG marker"
                    )

                code = reader.byte(position)
                position += 1

                if code == 0x00:
                    raise _JPEGParseError(
                        "Unexpected stuffed byte outside JPEG scan data"
                    )

            if code == 0xD9:
                if not saw_frame or not saw_scan:
                    raise _JPEGParseError(
                        "JPEG EOI found before a complete frame and scan"
                    )

                return ValidationResult(
                    True,
                    "JPEG marker structure and segment boundaries validated",
                    detected_size=position,
                )

            if code == 0xD8:
                raise _JPEGParseError(
                    "Unexpected nested JPEG SOI marker"
                )

            if code in self.STANDALONE_MARKERS:
                raise _JPEGParseError(
                    "Unexpected standalone JPEG marker"
                )

            # All remaining markers handled here have a 2-byte length.
            segment_length = reader.uint16(position)
            if segment_length < 2:
                raise _JPEGParseError(
                    "Invalid JPEG segment length"
                )

            segment_start = position + 2
            segment_end = position + segment_length

            if segment_end > limit:
                raise _JPEGParseError(
                    "JPEG segment extends beyond available candidate data"
                )

            if code in self.SOF_MARKERS:
                if saw_frame:
                    raise _JPEGParseError(
                        "Multiple JPEG frame headers are not supported"
                    )

                if segment_length < 8:
                    raise _JPEGParseError(
                        "JPEG frame header is too short"
                    )

                precision = reader.byte(segment_start)
                height = reader.uint16(segment_start + 1)
                width = reader.uint16(segment_start + 3)
                component_count = reader.byte(segment_start + 5)

                if precision == 0 or width == 0 or height == 0:
                    raise _JPEGParseError(
                        "Invalid JPEG frame precision or dimensions"
                    )

                if not 1 <= component_count <= 4:
                    raise _JPEGParseError(
                        "Invalid JPEG frame component count"
                    )

                expected_length = 8 + 3 * component_count
                if segment_length != expected_length:
                    raise _JPEGParseError(
                        "JPEG frame header length does not match its components"
                    )

                saw_frame = True

            elif code == 0xDA:  # Start of scan
                if not saw_frame:
                    raise _JPEGParseError(
                        "JPEG scan found before frame header"
                    )

                if segment_length < 6:
                    raise _JPEGParseError(
                        "JPEG scan header is too short"
                    )

                scan_components = reader.byte(segment_start)
                if not 1 <= scan_components <= component_count:
                    raise _JPEGParseError(
                        "Invalid JPEG scan component count"
                    )

                expected_length = 6 + 2 * scan_components
                if segment_length != expected_length:
                    raise _JPEGParseError(
                        "JPEG scan header length does not match its components"
                    )

                saw_scan = True
                in_scan = True

            elif code == 0xDB:  # Define quantization tables
                self._validate_dqt(reader, segment_start, segment_end)

            elif code == 0xC4:  # Define Huffman tables
                self._validate_dht(reader, segment_start, segment_end)

            elif code == 0xDD:  # Define restart interval
                if segment_length != 4:
                    raise _JPEGParseError(
                        "Invalid JPEG restart-interval segment length"
                    )

            position = segment_end

        raise _JPEGParseError(
            "JPEG EOI marker not found within available candidate data"
        )

    def _find_scan_marker(self, reader, position, limit):
        """Find a real marker in entropy-coded data, skipping FF00 and RSTn."""
        while position < limit:
            value = reader.byte(position)
            position += 1

            if value != 0xFF:
                continue

            marker_offset = position - 1

            while position < limit and reader.byte(position) == 0xFF:
                position += 1

            if position >= limit:
                raise _JPEGParseError(
                    "Truncated marker in JPEG scan data"
                )

            code = reader.byte(position)
            position += 1

            if code == 0x00:
                # FF00 represents a literal FF byte in entropy-coded data.
                continue

            if 0xD0 <= code <= 0xD7:
                # Restart marker: scan data continues.
                continue

            return marker_offset, code, position

        raise _JPEGParseError(
            "JPEG scan ended without a terminating marker"
        )

    def _validate_dqt(self, reader, position, end):
        if position >= end:
            raise _JPEGParseError("Empty JPEG quantization-table segment")

        while position < end:
            info = reader.byte(position)
            position += 1

            precision = info >> 4
            table_id = info & 0x0F

            if precision not in (0, 1) or table_id > 3:
                raise _JPEGParseError(
                    "Invalid JPEG quantization-table descriptor"
                )

            table_bytes = 64 * (precision + 1)
            if position + table_bytes > end:
                raise _JPEGParseError(
                    "Truncated JPEG quantization table"
                )

            position += table_bytes

        if position != end:
            raise _JPEGParseError(
                "Invalid JPEG quantization-table segment boundary"
            )

    def _validate_dht(self, reader, position, end):
        if position >= end:
            raise _JPEGParseError("Empty JPEG Huffman-table segment")

        while position < end:
            info = reader.byte(position)
            position += 1

            table_class = info >> 4
            table_id = info & 0x0F

            if table_class not in (0, 1) or table_id > 3:
                raise _JPEGParseError(
                    "Invalid JPEG Huffman-table descriptor"
                )

            if position + 16 > end:
                raise _JPEGParseError(
                    "Truncated JPEG Huffman code-length counts"
                )

            counts = reader.read(position, 16)
            position += 16
            symbol_count = sum(counts)

            if symbol_count == 0 or position + symbol_count > end:
                raise _JPEGParseError(
                    "Invalid or truncated JPEG Huffman symbols"
                )

            position += symbol_count

        if position != end:
            raise _JPEGParseError(
                "Invalid JPEG Huffman-table segment boundary"
            )
