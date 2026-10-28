"""Filesystem locations used by the forensic engine.

Paths are anchored to the engine's own folder, never to the process's
working directory, so the engine behaves the same no matter where it
is launched from (terminal, tests, or the Suraksha desktop app).
"""
import os
import re
from pathlib import Path

# mft_parser/
ENGINE_ROOT = Path(__file__).resolve().parent.parent

# Where case databases are created when no directory is supplied.
# SURAKSHA_CASES_DIR lets a host application choose a writable location.
DEFAULT_CASES_DIR = Path(
    os.environ.get("SURAKSHA_CASES_DIR") or ENGINE_ROOT / "cases"
)

_UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {"CON", "PRN", "AUX", "NUL",
             *(f"COM{n}" for n in range(1, 10)), *(f"LPT{n}" for n in range(1, 10))}


def safe_filename(name, fallback="case"):
    """A file name valid on Windows that cannot leave its directory."""
    name = _UNSAFE.sub("_", name or "").strip().rstrip(" .")
    if name in ("", ".", ".."):
        name = fallback
    if name.split(".")[0].upper() in _RESERVED:
        name = "_" + name
    return name[:120]
