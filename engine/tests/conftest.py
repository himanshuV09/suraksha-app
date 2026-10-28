"""Shared pytest fixtures.

Most tests build their own tiny NTFS images (see tests/support), so the
suite runs anywhere. A few tests check exact facts about one particular
evidence image (test.001); they run only when MFT_TEST_IMAGE points at
that file, and are skipped otherwise:

    set MFT_TEST_IMAGE=D:\\evidence\\test.001
    python -m pytest
"""
import os

import pytest

REAL_IMAGE_ENV = "MFT_TEST_IMAGE"


@pytest.fixture
def real_image_path():
    path = os.environ.get(REAL_IMAGE_ENV)

    if not path:
        pytest.skip(f"set {REAL_IMAGE_ENV} to run tests against test.001")

    if not os.path.isfile(path):
        pytest.skip(f"{REAL_IMAGE_ENV} points to a missing file: {path}")

    return path


@pytest.fixture(autouse=True)
def _isolated_cases_dir(tmp_path, monkeypatch):
    """Never let a test write case databases into the real cases/ folder."""
    import engine.paths
    import database.case_database

    cases_dir = tmp_path / "cases"
    monkeypatch.setattr(engine.paths, "DEFAULT_CASES_DIR", cases_dir)
    monkeypatch.setattr(database.case_database, "DEFAULT_CASES_DIR", cases_dir)
