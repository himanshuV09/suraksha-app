"""Files carved from free space can be previewed and exported, hash-checked."""
import hashlib
import json
from pathlib import Path

import main_cli
from support.jpeg_samples import TINY_JPEG
from support.ntfs_image import FileSpec, NtfsImageBuilder


def run(capsys, *argv):
    exit_code = main_cli.main([str(arg) for arg in argv])
    return exit_code, json.loads(capsys.readouterr().out)


def carve(tmp_path, capsys):
    builder = NtfsImageBuilder()
    builder.add_file(FileSpec(record_number=16, name="a.txt", data=b"a"))
    builder.add_unallocated_payload("jpeg", 100, TINY_JPEG)
    image = builder.build(tmp_path / "carve.img")
    _, result = run(capsys, "analyze", image.path, "--cases-dir", tmp_path / "cases")
    db, case_id = result["database_path"], result["case_id"]
    exit_code, recovery = run(capsys, "recover-unallocated", image.path, db, case_id)
    assert exit_code == 0 and recovery["recovered_count"] == 1
    return image, db, case_id, recovery["artifacts"][0]["artifact_id"]


def test_preview_returns_the_image_and_verifies_its_hash(tmp_path, capsys):
    image, db, case_id, artifact_id = carve(tmp_path, capsys)

    exit_code, preview = run(capsys, "recovered-preview", image.path, db, case_id, artifact_id)

    assert exit_code == 0, preview
    assert preview["type"] == "image"
    assert preview["previewUrl"].startswith("data:image/jpeg;base64,")
    assert preview["hash_verified"] is True


def test_export_writes_files_and_manifest(tmp_path, capsys):
    image, db, case_id, artifact_id = carve(tmp_path, capsys)

    exit_code, result = run(capsys, "export-recovered", image.path, db, case_id, tmp_path / "out")

    assert exit_code == 0, result
    assert result["exported_count"] == 1 and result["hash_mismatches"] == 0
    exported = Path(result["files"][0]["path"])
    assert exported.read_bytes() == TINY_JPEG
    assert exported.name == f"recovered_{artifact_id}_{100 * 4096}.jpg"
    manifest = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))
    assert manifest["files"][0]["sha256"] == hashlib.sha256(TINY_JPEG).hexdigest()


def test_changed_image_is_reported_as_hash_mismatch(tmp_path, capsys):
    image, db, case_id, _ = carve(tmp_path, capsys)
    data = bytearray(Path(image.path).read_bytes())
    data[100 * 4096 + 200] ^= 0xFF  # alter one byte of the carved file
    Path(image.path).write_bytes(bytes(data))

    _, result = run(capsys, "export-recovered", image.path, db, case_id, tmp_path / "out")

    assert result["hash_mismatches"] == 1
    assert result["files"][0]["hash_verified"] is False


def test_unknown_artifact_id_is_not_found(tmp_path, capsys):
    image, db, case_id, _ = carve(tmp_path, capsys)

    exit_code, result = run(capsys, "recovered-preview", image.path, db, case_id, 999)

    assert exit_code == 1 and result["error_type"] == "NotFoundError"
