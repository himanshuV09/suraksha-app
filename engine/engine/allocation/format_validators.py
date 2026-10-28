"""Structural validators for carving PNG, GIF, PDF, ZIP (Office) and GZIP.

Each validator walks the format's own structure from the signature and
returns the exact file size, or raises FormatError. They never trust a
single magic number: every format is checked with an internal
consistency test that random data practically never passes:

    PNG   chunk CRC-32s, IHDR first, ends at IEND
    GIF   block structure from header to the 0x3B trailer
    PDF   startxref points at an xref table/stream, ends at %%EOF
    ZIP   end-of-central-directory points back at a central directory
          whose entries point at local headers (sizes follow from it)
    GZIP  the deflate stream decompresses and matches its CRC-32/ISIZE

All reads go through BoundedReader, so a validator can never read past
the candidate's region or the validation limit.
"""
import re
import struct
import zlib


class FormatError(Exception):
    """The candidate is not a complete, well-formed file of its type."""


class BoundedReader:
    """Chunk-cached reads limited to one candidate and its scan limit."""

    def __init__(self, context, limit, chunk_size=1024 * 1024):
        self.context = context
        self.limit = limit
        self.chunk_size = chunk_size
        self.cache_start = -1
        self.cache = b""

    def read(self, offset, size):
        if offset < 0 or size < 0 or offset + size > self.limit:
            raise FormatError("data is truncated or exceeds the validation limit")
        output = bytearray()
        position, end = offset, offset + size
        while position < end:
            if not self.cache_start <= position < self.cache_start + len(self.cache):
                self.cache_start = position
                amount = min(self.chunk_size, self.limit - position)
                try:
                    self.cache = self.context.read(amount, relative_offset=position)
                except (IOError, OSError, ValueError) as error:
                    raise FormatError("unable to read candidate data") from error
                if not self.cache:
                    raise FormatError("unexpected end of data")
            start = position - self.cache_start
            amount = min(end - position, len(self.cache) - start)
            output += self.cache[start:start + amount]
            position += amount
        return bytes(output)

    def read_upto(self, offset, size):
        """Like read(), but stops quietly at the limit."""
        return self.read(offset, max(0, min(size, self.limit - offset)))

    def find(self, needle, start, end=None, window=1024 * 1024):
        """Offset of ``needle`` in [start, end), or -1. Reads in windows."""
        end = self.limit if end is None else min(end, self.limit)
        position = start
        while position < end:
            data = self.read_upto(position, min(window + len(needle) - 1, end - position))
            index = data.find(needle)
            if index >= 0 and position + index + len(needle) <= end:
                return position + index
            if len(data) < len(needle):
                return -1
            position += window
        return -1


# ----------------------------------------------------------------------
# PNG
# ----------------------------------------------------------------------

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def validate_png(reader):
    if reader.read(0, 8) != PNG_SIGNATURE:
        raise FormatError("PNG signature mismatch")

    position = 8
    first = True
    while True:
        length, chunk_type = struct.unpack(">I4s", reader.read(position, 8))
        if not chunk_type.isalpha():
            raise FormatError(f"invalid PNG chunk type {chunk_type!r}")
        if length > reader.limit:
            raise FormatError("PNG chunk length exceeds the validation limit")
        if first:
            if chunk_type != b"IHDR" or length != 13:
                raise FormatError("PNG does not start with a valid IHDR chunk")
            width, height = struct.unpack(">II", reader.read(position + 8, 8))
            if not width or not height:
                raise FormatError("PNG image has zero width or height")
            first = False

        data = reader.read(position + 8, length)
        stored_crc = struct.unpack(">I", reader.read(position + 8 + length, 4))[0]
        if zlib.crc32(chunk_type + data) != stored_crc:
            raise FormatError(f"PNG {chunk_type.decode()} chunk CRC mismatch")

        position += 12 + length
        if chunk_type == b"IEND":
            return position, "PNG chunk structure and CRC-32 checksums validated"


# ----------------------------------------------------------------------
# GIF
# ----------------------------------------------------------------------

def _skip_sub_blocks(reader, position):
    while True:
        size = reader.read(position, 1)[0]
        position += 1
        if size == 0:
            return position
        position += size


def validate_gif(reader):
    header = reader.read(0, 13)
    if header[:6] not in (b"GIF87a", b"GIF89a"):
        raise FormatError("GIF version header mismatch")
    width, height, packed = struct.unpack_from("<HHB", header, 6)
    if not width or not height:
        raise FormatError("GIF has zero width or height")

    position = 13
    if packed & 0x80:
        position += 3 * (2 << (packed & 0x07))  # global color table

    images = 0
    while True:
        block = reader.read(position, 1)[0]
        if block == 0x3B:  # trailer
            if not images:
                raise FormatError("GIF contains no image")
            return position + 1, "GIF block structure validated"
        if block == 0x21:  # extension: label, then sub-blocks
            position = _skip_sub_blocks(reader, position + 2)
        elif block == 0x2C:  # image descriptor
            descriptor = reader.read(position + 1, 9)
            local = descriptor[8]
            position += 10
            if local & 0x80:
                position += 3 * (2 << (local & 0x07))
            minimum_code_size = reader.read(position, 1)[0]
            if not 2 <= minimum_code_size <= 12:
                raise FormatError("invalid GIF LZW code size")
            position = _skip_sub_blocks(reader, position + 1)
            images += 1
        else:
            raise FormatError(f"unexpected GIF block 0x{block:02X}")


# ----------------------------------------------------------------------
# PDF
# ----------------------------------------------------------------------

PDF_HEADER = re.compile(rb"%PDF-([12])\.(\d)")
STARTXREF = re.compile(rb"startxref\s+(\d+)\s+%%EOF")
# An incremental update (a saved edit) appends another body that ends in
# its own %%EOF; look this far past an %%EOF for the next one.
PDF_UPDATE_LOOKAHEAD = 1024 * 1024


def validate_pdf(reader):
    if not PDF_HEADER.match(reader.read(0, 8)):
        raise FormatError("PDF version header mismatch")

    end = None
    search_from = 8
    while True:
        eof = reader.find(b"%%EOF", search_from,
                          None if end is None else end + PDF_UPDATE_LOOKAHEAD)
        if eof < 0:
            break
        next_header = reader.find(b"%PDF-", search_from, eof)
        if next_header >= 0:
            break  # a different PDF starts before this %%EOF

        tail = reader.read(max(0, eof - 64), eof + 5 - max(0, eof - 64))
        match = STARTXREF.search(tail)
        if match:
            xref = int(match.group(1))
            if 0 < xref < eof:
                target = reader.read_upto(xref, 32)
                if target.startswith(b"xref") or re.match(rb"\d+\s+\d+\s+obj", target):
                    end = eof + 5
        search_from = eof + 5

    if end is None:
        raise FormatError("PDF has no %%EOF with a valid startxref")

    # Include the line ending after the final %%EOF.
    trailing = reader.read_upto(end, 2)
    end += 2 if trailing == b"\r\n" else 1 if trailing[:1] in (b"\n", b"\r") else 0
    return end, "PDF header, startxref target and %%EOF validated"


# ----------------------------------------------------------------------
# ZIP and ZIP-based formats (Office Open XML, OpenDocument, JAR, APK...)
# ----------------------------------------------------------------------

EOCD = b"PK\x05\x06"
CENTRAL = b"PK\x01\x02"
LOCAL = b"PK\x03\x04"
MAX_CENTRAL_ENTRIES = 65535

ODF_TYPES = {
    b"application/vnd.oasis.opendocument.text": ".odt",
    b"application/vnd.oasis.opendocument.spreadsheet": ".ods",
    b"application/vnd.oasis.opendocument.presentation": ".odp",
    b"application/epub+zip": ".epub",
}


def _zip_kind(names, reader):
    """Refine .zip to the specific ZIP-based format from member names."""
    lowered = [name.lower() for name in names]
    if "[content_types].xml" in lowered:
        for prefix, extension in (("word/", ".docx"), ("xl/", ".xlsx"),
                                  ("ppt/", ".pptx"), ("visio/", ".vsdx")):
            if any(name.startswith(prefix) for name in lowered):
                return extension
    if "androidmanifest.xml" in lowered and "classes.dex" in lowered:
        return ".apk"
    if lowered and lowered[0] == "mimetype":
        # Stored first and uncompressed; the type follows the 30-byte header.
        name_length, extra_length = struct.unpack("<HH", reader.read(26, 4))
        start = 30 + name_length + extra_length
        mime = reader.read_upto(start, 64)
        for prefix, extension in ODF_TYPES.items():
            if mime.startswith(prefix):
                return extension
    if "meta-inf/manifest.mf" in lowered:
        return ".jar"
    return ".zip"


def validate_zip(reader):
    if reader.read(0, 4) != LOCAL:
        raise FormatError("ZIP local file header mismatch")

    search_from = 4
    while True:
        eocd = reader.find(EOCD, search_from)
        if eocd < 0:
            raise FormatError("no end-of-central-directory record that matches this archive")
        search_from = eocd + 4

        record = reader.read_upto(eocd, 22)
        if len(record) < 22:
            continue
        disk, cd_disk, _, entries, cd_size, cd_offset, comment_length = struct.unpack(
            "<HHHHIIH", record[4:22]
        )
        if cd_offset == 0xFFFFFFFF or entries == 0xFFFF:
            raise FormatError("ZIP64 archives are not supported yet")
        if disk or cd_disk or not entries or cd_offset + cd_size != eocd:
            continue  # belongs to another archive (or is a false match)

        names = []
        position = cd_offset
        try:
            for _ in range(entries):
                header = reader.read(position, 46)
                if header[:4] != CENTRAL:
                    raise FormatError("broken central directory")
                name_length, extra_length, comment = struct.unpack_from("<HHH", header, 28)
                local_offset = struct.unpack_from("<I", header, 42)[0]
                if not names and local_offset != 0:
                    raise FormatError("first entry does not start at the archive start")
                if reader.read(local_offset, 4) != LOCAL:
                    raise FormatError("central directory points at no local header")
                names.append(reader.read(position + 46, name_length).decode("cp437", "replace"))
                position += 46 + name_length + extra_length + comment
        except FormatError:
            continue
        if position != eocd:
            continue

        size = eocd + 22 + comment_length
        return size, "ZIP central directory and local headers validated", _zip_kind(names, reader)


# ----------------------------------------------------------------------
# GZIP
# ----------------------------------------------------------------------

GZIP_MAX_OUTPUT = 1024 * 1024 * 1024  # stop decompressing bombs


def validate_gzip(reader):
    header = reader.read(0, 10)
    if header[:3] != b"\x1f\x8b\x08":
        raise FormatError("GZIP header mismatch (only deflate is defined)")
    flags, _, extra_flags, os_code = header[3], header[4:8], header[8], header[9]
    if flags & 0xE0:
        raise FormatError("GZIP reserved flag bits are set")
    if extra_flags not in (0, 2, 4) or (os_code > 13 and os_code != 255):
        raise FormatError("GZIP header fields out of range")

    position = 10
    if flags & 0x04:  # FEXTRA
        position += 2 + struct.unpack("<H", reader.read(position, 2))[0]
    for flag in (0x08, 0x10):  # FNAME, FCOMMENT: zero-terminated
        if flags & flag:
            terminator = reader.find(b"\x00", position, position + 65536)
            if terminator < 0:
                raise FormatError("unterminated GZIP name/comment")
            position = terminator + 1
    if flags & 0x02:  # FHCRC
        position += 2

    decompressor = zlib.decompressobj(-zlib.MAX_WBITS)
    crc = output_size = 0
    while not decompressor.eof:
        chunk = reader.read_upto(position, 256 * 1024)
        if not chunk:
            raise FormatError("GZIP deflate stream is truncated")
        try:
            output = decompressor.decompress(chunk)
        except zlib.error as error:
            raise FormatError(f"GZIP deflate stream is invalid: {error}") from error
        crc = zlib.crc32(output, crc)
        output_size += len(output)
        if output_size > GZIP_MAX_OUTPUT:
            raise FormatError("GZIP output exceeds the decompression limit")
        position += len(chunk) - len(decompressor.unused_data)

    stored_crc, stored_size = struct.unpack("<II", reader.read(position, 8))
    if stored_crc != crc or stored_size != output_size & 0xFFFFFFFF:
        raise FormatError("GZIP CRC-32 or length does not match the data")
    return position + 8, "GZIP deflate stream, CRC-32 and length validated"


VALIDATORS = {
    "PNG": validate_png,
    "GIF": validate_gif,
    "PDF": validate_pdf,
    "ZIP": validate_zip,
    "GZIP": validate_gzip,
}
