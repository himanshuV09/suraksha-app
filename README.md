# Suraksha

[![CI](https://github.com/himanshuV09/suraksha-app/actions/workflows/ci.yml/badge.svg)](https://github.com/himanshuV09/suraksha-app/actions/workflows/ci.yml)

A desktop workstation for NTFS disk-image forensics. Suraksha reads raw
disk images (`.001`, `.dd`, `.img`, `.raw`) **read-only** and lets an
investigator browse the file system, recover deleted files, carve files
from free space, inspect NTFS metafiles and build a timeline.

## What it does

| Area | Capabilities |
|---|---|
| **Volumes** | Bare NTFS volumes and MBR/GPT partitioned disks; fragmented `$MFT`; malformed records skipped and reported |
| **File system** | Every MFT record (live and deleted), full paths, timestamps, alternate data streams, ZIP/Office container contents, previews (text, images, DOCX, PPTX) |
| **Deleted files** | Graded *recoverable / partial / overwritten* against `$Bitmap`, against later-written deleted files, and by content type checks; restored with original names, timestamps, SHA-256 and a manifest of unreliable byte ranges |
| **Free space** | Carving of JPEG, PNG, GIF, PDF, ZIP/DOCX/XLSX/PPTX and GZIP with structural validation; reassembly of fragmented files for formats with integrity checks; hash-verified preview and export |
| **Metafiles** | `$MFT`, `$MFTMirr`, `$LogFile`, `$Volume`, `$AttrDef`, `$Bitmap`, `$Boot`, `$BadClus`, `$Secure`, `$UpCase`, the whole `$Extend` tree (`$UsnJrnl`, `$ObjId`, `$Quota`, `$Reparse`, `$Deleted`, `$RmMetadata`), reserved records 12-23 |
| **Timeline** | MFT timestamps plus USN journal, `$LogFile`, `$I30` index slack and MFT-record slack events |
| **Slack** | File slack (with readable strings) and MFT record slack |

## Repository layout

```
app/                 Desktop application
  src/               React + TypeScript user interface
  src-tauri/         Rust (Tauri 2) shell: runs the engine, streams progress
engine/              Forensic engine (Python 3.12)
  main_cli.py        Command-line entry point (JSON contract, see docs/)
  engine/            Analysis pipeline, metafiles, recovery, APIs
  parsers/ database/ NTFS record parsing; SQLite case storage
  tests/             pytest suite (builds synthetic NTFS images)
  suraksha-engine.spec   PyInstaller build of the engine
scripts/             build.ps1, dev.ps1, test.ps1
docs/                Architecture and engine command reference
```

## Development

Prerequisites: Python 3.12, Node.js 20+, Rust stable with the
[Tauri prerequisites](https://tauri.app/start/prerequisites/) for Windows.

```powershell
git clone https://github.com/himanshuV09/suraksha-app.git
cd suraksha-app
python -m pip install -r engine/requirements-dev.txt
.\scripts\dev.ps1        # starts the app; the engine runs from source
.\scripts\test.ps1       # engine tests, type check, Rust tests
```

The engine can also be used on its own:

```powershell
cd engine
python main_cli.py analyze D:\evidence\usb.001 --case-name "Case 41" --investigator "R. Rao"
python main_cli.py list-cases
```

Tests that need the original `test.001` evidence image run only when
`MFT_TEST_IMAGE` points to it; every other test builds its own image.

## Building the installers

```powershell
.\scripts\build.ps1
```

This runs the tests, builds the engine into a standalone executable
(PyInstaller, so users do not need Python), places it in the app's
resources and produces `app/src-tauri/target/release/bundle/nsis/*.exe`
and `.../msi/*.msi`.

## Where data is kept

| What | Location |
|---|---|
| Case databases | `%APPDATA%\com.pc-shagun.suraksha\cases\` |
| Engine log | `%LOCALAPPDATA%\com.pc-shagun.suraksha\logs\engine.log` (rotated at 5 MB) |

Both are shown, with links, at the bottom of the Cases screen.

## Forensic safety

* Evidence images are opened read-only; nothing is ever written to them.
* Recovered and exported files carry SHA-256 hashes in a manifest;
  carved files are re-hashed against the value recorded at recovery.
* Restores never overwrite existing files.
* Case listing opens databases read-only.
