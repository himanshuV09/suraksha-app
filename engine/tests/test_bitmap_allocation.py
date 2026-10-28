import io

import pytest

from engine.allocation.bitmap import (
    BitmapAllocationError,
    decode_bitmap,
    load_bitmap,
    read_data_runs,
)


def test_decode_bitmap_uses_ntfs_lsb_first_bit_order():
    # Bits 0 and 2 are allocated; bits 1 and 3 are unallocated.
    ranges = decode_bitmap(bytes([0b00000101]), 4)

    assert ranges == [
        {
            "start_cluster": 0,
            "cluster_count": 1,
            "end_cluster": 0,
            "state": "allocated",
        },
        {
            "start_cluster": 1,
            "cluster_count": 1,
            "end_cluster": 1,
            "state": "unallocated",
        },
        {
            "start_cluster": 2,
            "cluster_count": 1,
            "end_cluster": 2,
            "state": "allocated",
        },
        {
            "start_cluster": 3,
            "cluster_count": 1,
            "end_cluster": 3,
            "state": "unallocated",
        },
    ]


def test_decode_bitmap_ignores_padding_bits_after_last_cluster():
    # Only clusters 0-2 exist for this test. The remaining bits are padding.
    ranges = decode_bitmap(bytes([0b11111000]), 3)

    assert ranges == [
        {
            "start_cluster": 0,
            "cluster_count": 3,
            "end_cluster": 2,
            "state": "unallocated",
        }
    ]


def test_decode_bitmap_rejects_insufficient_data():
    with pytest.raises(BitmapAllocationError):
        decode_bitmap(b"", 1)


def test_read_data_runs_applies_volume_offset():
    image = io.BytesIO(b"_" * 32 + b"ABCDEFGH" + b"_" * 32)

    runs = [{"length": 2, "lcn": 2, "sparse": False}]

    result = read_data_runs(
        image=image,
        runs=runs,
        cluster_size=4,
        real_size=8,
        volume_offset=24,
    )

    # Physical offset = 24 + (2 * 4) = 32.
    assert result == b"ABCDEFGH"


def test_read_data_runs_rejects_incomplete_physical_read():
    image = io.BytesIO(b"short")

    runs = [{"length": 2, "lcn": 1, "sparse": False}]

    with pytest.raises(BitmapAllocationError):
        read_data_runs(
            image=image,
            runs=runs,
            cluster_size=4,
            real_size=8,
        )


def test_read_data_runs_zero_fills_sparse_runs():
    image = io.BytesIO(b"ABCDEFGH")

    runs = [
        {"length": 1, "lcn": 0, "sparse": False},
        {"length": 1, "lcn": None, "sparse": True},
    ]

    result = read_data_runs(
        image=image,
        runs=runs,
        cluster_size=4,
        real_size=8,
    )

    assert result == b"ABCD" + b"\x00" * 4


def test_load_bitmap_returns_exact_logical_size():
    image = io.BytesIO(b"ABCDEFGH")

    result = load_bitmap(
        image=image,
        bitmap_runs=[{"length": 2, "lcn": 0, "sparse": False}],
        cluster_size=4,
        bitmap_size=5,
    )

    assert result == b"ABCDE"
    assert len(result) == 5


@pytest.mark.parametrize("volume_offset", [-1, True, 1.5, "4"])
def test_read_data_runs_rejects_invalid_volume_offset(volume_offset):
    with pytest.raises(BitmapAllocationError):
        read_data_runs(
            image=io.BytesIO(b"ABCDEFGH"),
            runs=[{"length": 1, "lcn": 0, "sparse": False}],
            cluster_size=4,
            real_size=4,
            volume_offset=volume_offset,
        )
