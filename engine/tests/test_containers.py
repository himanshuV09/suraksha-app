"""ZIP-based containers are listed and previewed straight from the image."""
import io
import json
import sqlite3
import zipfile

import main_cli
from support.ntfs_image import FileSpec, NtfsImageBuilder

MEMBER = "word/media/photo.bin"
MEMBER_BYTES = bytes(range(256)) * 40


def make_docx():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/", "")  # explicit folder entry
        archive.writestr("word/document.xml", "<w:document/>" * 200)
        archive.writestr(MEMBER, MEMBER_BYTES)
    return buffer.getvalue()


def run(capsys, *argv):
    exit_code = main_cli.main([str(arg) for arg in argv])
    return exit_code, json.loads(capsys.readouterr().out)


def test_docx_members_are_listed_and_previewable(tmp_path, capsys):
    docx = make_docx()
    clusters = -(-len(docx) // 4096)
    builder = NtfsImageBuilder()
    # Split across two fragments so the stream must follow data runs.
    first = clusters // 2 or 1
    builder.add_file(FileSpec(
        record_number=16, name="report.docx", data=docx,
        runs=[(60, first), (120, clusters - first)],
    ))
    builder.add_file(FileSpec(record_number=17, name="notes.txt", data=b"not a zip"))
    image = builder.build(tmp_path / "docs.img")

    exit_code, result = run(capsys, "analyze", image.path, "--cases-dir", tmp_path / "cases")
    assert exit_code == 0, result

    rows = sqlite3.connect(result["database_path"]).execute(
        "SELECT path, directory FROM container_artifacts ORDER BY path"
    ).fetchall()
    paths = [path for path, _ in rows]

    assert MEMBER in paths and "word/document.xml" in paths
    assert paths.count("word") == 1  # explicit folder entry is not duplicated

    _, evidence = run(capsys, "evidence", result["database_path"], result["case_id"])
    evidence_id = next(e["evidence_id"] for e in evidence["evidence"] if e["filename"] == "report.docx")

    exit_code, preview = run(capsys, "preview", result["database_path"], evidence_id, MEMBER)
    assert exit_code == 0, preview
    assert preview["size"] == len(MEMBER_BYTES)
