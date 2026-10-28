import struct
import pytest

from ntfs import parse_boot_sector


def make_boot_sector(
    bytes_per_sector=512,
    sectors_per_cluster=8,
    total_sectors=7864191,
    clusters_per_file_record=-10,
    clusters_per_index_buffer=1,
):
    """Build a minimal synthetic NTFS boot sector for unit testing."""
    data = bytearray(512)
    data[3:11] = b"NTFS    "

    struct.pack_into("<H", data, 11, bytes_per_sector)
    data[13] = sectors_per_cluster
    struct.pack_into("<Q", data, 40, total_sectors)
    struct.pack_into("<Q", data, 48, 10)
    struct.pack_into("<Q", data, 56, 20)
    struct.pack_into("<b", data, 64, clusters_per_file_record)
    struct.pack_into("<b", data, 68, clusters_per_index_buffer)
    struct.pack_into("<Q", data, 72, 12345)

    return bytes(data)


def test_valid_ntfs_boot_sector_geometry():
    info = parse_boot_sector(make_boot_sector())

    assert info["bytes_per_sector"] == 512
    assert info["sectors_per_cluster"] == 8
    assert info["cluster_size"] == 4096
    assert info["total_sectors"] == 7864191
    assert info["volume_size_bytes"] == 7864191 * 512
    assert info["total_clusters"] == 7864191 // 8
    assert info["mft_cluster"] == 10
    assert info["mft_mirror_cluster"] == 20


def test_rejects_short_boot_sector():
    with pytest.raises(ValueError):
        parse_boot_sector(b"NTFS")


def test_rejects_wrong_filesystem_identifier():
    data = bytearray(make_boot_sector())
    data[3:11] = b"FAT32   "

    with pytest.raises(ValueError):
        parse_boot_sector(bytes(data))


@pytest.mark.parametrize("bytes_per_sector", [0])
def test_rejects_zero_bytes_per_sector(bytes_per_sector):
    with pytest.raises(ValueError):
        parse_boot_sector(make_boot_sector(
            bytes_per_sector=bytes_per_sector
        ))


def test_rejects_zero_sectors_per_cluster():
    with pytest.raises(ValueError):
        parse_boot_sector(make_boot_sector(sectors_per_cluster=0))


def test_rejects_zero_total_sectors():
    with pytest.raises(ValueError):
        parse_boot_sector(make_boot_sector(total_sectors=0))


def test_preserves_partial_final_cluster_geometry():
    info = parse_boot_sector(make_boot_sector(
        total_sectors=7864191,
        sectors_per_cluster=8,
    ))

    # The volume has 7 sectors beyond its final complete cluster.
    assert info["total_clusters"] == 983023
    assert (
        info["volume_size_bytes"]
        - info["total_clusters"] * info["cluster_size"]
    ) == 7 * info["bytes_per_sector"]

@pytest.mark.parametrize(
    "bytes_per_sector",
    [128, 256, 1000, 8192],
)
def test_rejects_unsupported_bytes_per_sector(bytes_per_sector):
    with pytest.raises(ValueError):
        parse_boot_sector(make_boot_sector(
            bytes_per_sector=bytes_per_sector
        ))


@pytest.mark.parametrize(
    "sectors_per_cluster",
    [3, 6, 7, 9, 255],
)
def test_rejects_invalid_sectors_per_cluster(sectors_per_cluster):
    with pytest.raises(ValueError):
        parse_boot_sector(make_boot_sector(
            sectors_per_cluster=sectors_per_cluster
        ))


def test_rejects_zero_mft_record_size_encoding():
    with pytest.raises(ValueError):
        parse_boot_sector(
            make_boot_sector(clusters_per_file_record=0)
        )


def test_accepts_positive_mft_record_size_encoding():
    result = parse_boot_sector(
        make_boot_sector(clusters_per_file_record=1)
    )

    assert result["clusters_per_file_record"] == 1
    assert result["cluster_size"] == 4096


@pytest.mark.parametrize(
    "clusters_per_file_record",
    [-32, -1],
)
def test_rejects_out_of_range_mft_record_size_encoding(
    clusters_per_file_record,
):
    with pytest.raises(ValueError):
        parse_boot_sector(make_boot_sector(
            clusters_per_file_record=clusters_per_file_record
        ))
