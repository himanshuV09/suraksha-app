"""Carving PNG, GIF, PDF, ZIP/Office and GZIP from free space."""
import gzip
import io
import json
import random
import struct
import zipfile
import zlib
from pathlib import Path

import pytest

import main_cli
from support.jpeg_samples import TINY_JPEG
from support.ntfs_image import FileSpec, NtfsImageBuilder

CLUSTER = 4096


# ----------------------------------------------------------------------
# Sample files, built byte by byte
# ----------------------------------------------------------------------

def png_file(width=4, height=3):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    raw = b"".join(b"\x00" + bytes(width * 3) for _ in range(height))
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw))
            + chunk(b"IEND", b""))


def gif_file():
    # 1x1 GIF89a with a 2-color global table and one image.
    return (b"GIF89a" + struct.pack("<HHBBB", 1, 1, 0x80, 0, 0)
            + b"\x00\x00\x00\xff\xff\xff"
            + b"\x21\xf9\x04\x00\x00\x00\x00\x00"           # graphic control ext
            + b"\x2c" + struct.pack("<HHHHB", 0, 0, 1, 1, 0)
            + b"\x02\x02\x44\x01\x00"                        # LZW data
            + b"\x3b")


def pdf_file(updates=0):
    body = b"%PDF-1.4\n1 0 obj << /Type /Catalog >> endobj\n"
    xref = len(body)
    pdf = body + b"xref\n0 2\n0000000000 65535 f \n0000000009 00000 n \ntrailer << /Root 1 0 R >>\n"
    pdf += b"startxref\n%d\n%%%%EOF\n" % xref
    for number in range(updates):  # incremental saves append more bodies
        obj = b"%d 0 obj << /Update %d >> endobj\n" % (number + 2, number)
        xref = len(pdf) + len(obj)
        pdf += obj + b"xref\n0 1\n0000000000 65535 f \ntrailer << >>\nstartxref\n%d\n%%%%EOF\n" % xref
    return pdf


def zip_file(kind="docx"):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        if kind == "docx":
            archive.writestr("[Content_Types].xml", "<Types/>")
            archive.writestr("word/document.xml", "<w:document>" + "x" * 3000 + "</w:document>")
            archive.writestr("word/media/photo.jpg", TINY_JPEG)  # nested JPEG
        else:
            archive.writestr("readme.txt", "plain zip")
    return buffer.getvalue()


def gzip_file():
    return gzip.compress(b"log line\n" * 2000, mtime=0)


def noise(size, seed):
    return random.Random(seed).randbytes(size)


# ----------------------------------------------------------------------
# End to end
# ----------------------------------------------------------------------

def run(capsys, *argv):
    exit_code = main_cli.main([str(arg) for arg in argv])
    return exit_code, json.loads(capsys.readouterr().out)


def carve(tmp_path, capsys, payloads):
    """Place each payload (followed by random data) in free clusters."""
    builder = NtfsImageBuilder()
    builder.add_file(FileSpec(record_number=16, name="a.txt", data=b"a"))
    lcn = 40
    for index, payload in enumerate(payloads):
        builder.add_unallocated_payload(f"p{index}", lcn, payload + noise(300, index))
        lcn += -(-(len(payload) + 300) // CLUSTER) + 1
    image = builder.build(tmp_path / "carve.img")
    _, result = run(capsys, "analyze", image.path, "--cases-dir", tmp_path / "cases")
    db, case_id = result["database_path"], result["case_id"]
    exit_code, recovery = run(capsys, "recover-unallocated", image.path, db, case_id)
    assert exit_code == 0, recovery
    _, export = run(capsys, "export-recovered", image.path, db, case_id, tmp_path / "out")
    files = {Path(item["path"]).suffix: Path(item["path"]).read_bytes() for item in export["files"]}
    return recovery, files


def test_every_supported_format_is_carved_exactly(tmp_path, capsys):
    samples = {
        ".png": png_file(),
        ".gif": gif_file(),
        ".pdf": pdf_file(updates=2),
        ".docx": zip_file("docx"),
        ".zip": zip_file("zip"),
        ".gz": gzip_file(),
        ".jpg": TINY_JPEG,
    }

    recovery, files = carve(tmp_path, capsys, list(samples.values()))

    assert recovery["recovered_by_type"] == {extension: 1 for extension in samples}
    for extension, original in samples.items():
        assert files[extension] == original, extension
    # The JPEG inside the .docx is part of it, not a separate file.
    assert recovery["candidates_nested"] >= 1


@pytest.mark.parametrize("name, payload", [
    ("PNG with a flipped byte", png_file()[:40] + b"\x00" + png_file()[41:]),
    ("ZIP cut short", zip_file("zip")[:-30]),
    ("GZIP header on random data", b"\x1f\x8b\x08\x00" + bytes(6) + noise(2000, 7)),
    ("PDF without startxref", b"%PDF-1.7\n1 0 obj<<>>endobj\n%%EOF\n"),
    ("GIF without trailer", gif_file()[:-1] + b"\x99"),
])
def test_damaged_files_are_rejected(tmp_path, capsys, name, payload):
    recovery, _ = carve(tmp_path, capsys, [payload])

    assert recovery["recovered_count"] == 0, name


def test_gzip_signature_needs_the_deflate_method_byte(tmp_path, capsys):
    # Random data contains 1F 8B often; 1F 8B 08 far less often.
    recovery, _ = carve(tmp_path, capsys, [b"\x1f\x8b\x00\x00" * 50])

    assert recovery["candidates_detected"] == 0
