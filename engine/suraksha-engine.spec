# PyInstaller build of the forensic engine (one-folder, console).
#
#   pyinstaller suraksha-engine.spec --noconfirm
#
# Produces dist/suraksha-engine/suraksha-engine.exe plus its _internal
# folder. scripts/build.ps1 copies that folder into the Tauri resources.
#
# One-folder rather than one-file: a one-file build unpacks itself to a
# temporary folder on every start, and the app starts the engine for
# each action (every hex-view page), so that would add ~1 s per click.
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH)

# main_cli imports command modules lazily (importlib), which PyInstaller
# cannot see, so list every engine module explicitly.
hidden = []
for package in ("engine", "database", "parsers"):
    hidden += collect_submodules(package)
hidden += [path.stem for path in ROOT.glob("*.py") if path.stem != "main_cli"]

analysis = Analysis(
    [str(ROOT / "main_cli.py")],
    pathex=[str(ROOT)],
    hiddenimports=hidden,
    # Document templates used by the DOCX/PPTX preview.
    datas=collect_data_files("docx") + collect_data_files("pptx"),
    excludes=["tkinter", "pytest", "tests", "PIL.ImageQt", "PyQt5", "PySide6"],
    noarchive=False,
)

pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="suraksha-engine",
    console=True,  # stdout carries the JSON result
    upx=False,
)

COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    name="suraksha-engine",
    upx=False,
)
