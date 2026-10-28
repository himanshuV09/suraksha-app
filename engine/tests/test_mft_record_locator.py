import io

import pytest

from engine.volume.geometry import VolumeGeometry
from engine.volume.mft_locator import MftRecordLocator

RECORD = 1024


def _image_with_records(cluster_size, runs, record_count, volume_offset=0):
    """Lay out records 0..n-1, each filled with its own number, along runs."""
    total = volume_offset + max(lcn + length for lcn, length in runs) * cluster_size
    image = bytearray(total)
    stream = b"".join(bytes([n]) * RECORD for n in range(record_count))

    position = 0
    for lcn, length in runs:
        size = length * cluster_size
        start = volume_offset + lcn * cluster_size
        chunk = stream[position:position + size]
        image[start:start + len(chunk)] = chunk
        position += size

    return io.BytesIO(bytes(image))


def _locator(cluster_size, runs, record_count, volume_offset=0):
    return MftRecordLocator(
        data_runs=[{"lcn": lcn, "length": length, "sparse": False} for lcn, length in runs],
        geometry=VolumeGeometry(volume_offset=volume_offset, cluster_size=cluster_size),
        record_size=RECORD,
        mft_size=record_count * RECORD,
    )


def test_reads_records_from_every_run_of_a_fragmented_mft():
    runs = [(4, 2), (200, 2)]  # 8 records per run
    image = _image_with_records(4096, runs, 16)
    locator = _locator(4096, runs, 16)

    for record_number in range(16):
        assert locator.read(image, record_number) == bytes([record_number]) * RECORD

    assert locator.is_fragmented


def test_stitches_a_record_that_straddles_two_runs():
    runs = [(10, 3), (50, 5)]  # 512-byte clusters: record 1 = cluster 12 + cluster 50
    image = _image_with_records(512, runs, 4)
    locator = _locator(512, runs, 4)

    assert locator.read(image, 1) == b"\x01" * RECORD


def test_applies_the_partition_offset():
    runs = [(4, 1), (100, 1)]
    image = _image_with_records(4096, runs, 8, volume_offset=65536)
    locator = _locator(4096, runs, 8, volume_offset=65536)

    assert locator.read(image, 5) == b"\x05" * RECORD
    assert locator.record_offset(4) == 65536 + 100 * 4096


def test_records_outside_the_mapped_stream_read_as_empty():
    locator = _locator(4096, [(4, 1)], 4)

    assert locator.read(io.BytesIO(bytes(8 * 4096)), 4) == b""
    assert locator.record_count == 4


def test_rejects_an_mft_without_runs():
    with pytest.raises(ValueError):
        MftRecordLocator([], VolumeGeometry(0, 4096), RECORD, RECORD)
