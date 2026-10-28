
import struct


def parse_boot_sector(boot_sector):
    if not isinstance(boot_sector, (bytes, bytearray)):
        raise TypeError("boot_sector must be bytes or bytearray")

    if len(boot_sector) < 512:
        raise ValueError("NTFS boot sector must contain at least 512 bytes")

    oem_id = boot_sector[3:11].decode("ascii", errors="replace").strip()

    if oem_id != "NTFS":
        raise ValueError(f"Unsupported filesystem boot sector: {oem_id!r}")

    bytes_per_sector = struct.unpack_from("<H", boot_sector, 11)[0]
    sectors_per_cluster = boot_sector[13]
    total_sectors = struct.unpack_from("<Q", boot_sector, 40)[0]
    mft_cluster = struct.unpack_from("<Q", boot_sector, 48)[0]
    mft_mirror_cluster = struct.unpack_from("<Q", boot_sector, 56)[0]
    clusters_per_file_record = struct.unpack_from("<b", boot_sector, 64)[0]
    clusters_per_index_buffer = struct.unpack_from("<b", boot_sector, 68)[0]
    serial_number = struct.unpack_from("<Q", boot_sector, 72)[0]

    # Validate supported sector geometry.
    if bytes_per_sector not in (512, 1024, 2048, 4096):
        raise ValueError("Unsupported NTFS bytes-per-sector value")

    if (
        sectors_per_cluster < 1
        or sectors_per_cluster > 128
        or sectors_per_cluster & (sectors_per_cluster - 1)
    ):
        raise ValueError("Invalid NTFS sectors-per-cluster value")

    if total_sectors == 0:
        raise ValueError("Invalid NTFS total-sectors value")

    cluster_size = bytes_per_sector * sectors_per_cluster

    # NTFS cluster sizes must not exceed 64 KiB for this parser.
    if cluster_size > 65536:
        raise ValueError("Unsupported NTFS cluster size")

    total_clusters = total_sectors // sectors_per_cluster

    if total_clusters <= 0:
        raise ValueError("NTFS volume contains no complete clusters")

    # Validate MFT record-size encoding.
    if clusters_per_file_record < 0:
        record_size = 1 << abs(clusters_per_file_record)
    elif clusters_per_file_record > 0:
        record_size = clusters_per_file_record * cluster_size
    else:
        raise ValueError("Invalid NTFS MFT record-size encoding")

    # Keep the parser within a conservative, practical record-size bound.
    if record_size < 256 or record_size > 65536:
        raise ValueError("Unsupported NTFS MFT record size")

    # A positive index-buffer encoding represents a cluster count;
    # a negative encoding represents a byte size as a power of two.
    if clusters_per_index_buffer == 0:
        raise ValueError("Invalid NTFS index-buffer-size encoding")

    if clusters_per_index_buffer < 0:
        index_buffer_size = 1 << abs(clusters_per_index_buffer)
    else:
        index_buffer_size = clusters_per_index_buffer * cluster_size

    if index_buffer_size <= 0 or index_buffer_size > 65536:
        raise ValueError("Unsupported NTFS index-buffer size")

    volume_size_bytes = total_sectors * bytes_per_sector

    return {
        "oem_id": oem_id,
        "bytes_per_sector": bytes_per_sector,
        "sectors_per_cluster": sectors_per_cluster,
        "cluster_size": cluster_size,
        "total_sectors": total_sectors,
        "volume_size_bytes": volume_size_bytes,
        "total_clusters": total_clusters,
        "mft_cluster": mft_cluster,
        "mft_mirror_cluster": mft_mirror_cluster,
        "clusters_per_file_record": clusters_per_file_record,
        "clusters_per_index_buffer": clusters_per_index_buffer,
        "serial_number": serial_number,
    }
