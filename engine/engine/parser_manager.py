
import os
import struct

from ntfs import parse_boot_sector
from parsers.ntfs_parser import NTFSParser


class ParserManager:
    MBR_PARTITION_TABLE_OFFSET = 446
    MBR_PARTITION_ENTRY_SIZE = 16
    MBR_PARTITION_COUNT = 4
    GPT_HEADER_OFFSET = 512
    GPT_ENTRY_MIN_SIZE = 128

    def __init__(self, image, repository, case_id):
        self.image = image
        self.repository = repository
        self.case_id = case_id

        self.filesystem = None
        self.volume_offset = 0
        self.partition_info = None

    def _read_at(self, offset, size):
        if offset < 0 or size < 0:
            raise ValueError("Invalid image read bounds")

        self.image.seek(offset)
        return self.image.read(size)

    def _valid_ntfs_boot_sector(self, offset):
        image_size = os.fstat(self.image.fileno()).st_size

        if offset < 0 or offset + 512 > image_size:
            return None

        boot_sector = self._read_at(offset, 512)

        if len(boot_sector) != 512:
            return None

        if boot_sector[3:11] != b"NTFS    ":
            return None

        try:
            info = parse_boot_sector(boot_sector)
        except (ValueError, struct.error):
            return None

        volume_size = info["volume_size_bytes"]

        if volume_size <= 0 or offset + volume_size > image_size:
            return None

        # NTFS cluster and MFT metadata must fit within the declared volume.
        if info["cluster_size"] <= 0:
            return None

        if info["mft_cluster"] >= info["total_clusters"]:
            return None

        info["volume_offset"] = offset
        return info

    def _read_mbr_partitions(self):
        sector = self._read_at(0, 512)

        if len(sector) < 512 or sector[510:512] != b"\x55\xaa":
            return []

        partitions = []

        for index in range(self.MBR_PARTITION_COUNT):
            start = (
                self.MBR_PARTITION_TABLE_OFFSET
                + index * self.MBR_PARTITION_ENTRY_SIZE
            )
            entry = sector[start:start + self.MBR_PARTITION_ENTRY_SIZE]

            partition_type = entry[4]
            start_lba = struct.unpack_from("<I", entry, 8)[0]
            sector_count = struct.unpack_from("<I", entry, 12)[0]

            if partition_type == 0 or start_lba == 0 or sector_count == 0:
                continue

            # 0xEE is the protective MBR entry used by GPT.
            if partition_type == 0xEE:
                continue

            partitions.append({
                "scheme": "MBR",
                "partition_number": index + 1,
                "partition_type": partition_type,
                "start_lba": start_lba,
                "sector_count": sector_count,
                "sector_size": 512,
                "start_offset": start_lba * 512,
                "size_bytes": sector_count * 512,
            })

        return partitions

    def _read_gpt_partitions(self):
        header = self._read_at(self.GPT_HEADER_OFFSET, 512)

        if len(header) < 92 or header[:8] != b"EFI PART":
            return []

        header_size = struct.unpack_from("<I", header, 12)[0]
        entry_lba = struct.unpack_from("<Q", header, 72)[0]
        entry_count = struct.unpack_from("<I", header, 80)[0]
        entry_size = struct.unpack_from("<I", header, 84)[0]

        if not 92 <= header_size <= 512:
            return []

        if entry_count == 0 or entry_size < self.GPT_ENTRY_MIN_SIZE:
            return []

        image_size = os.fstat(self.image.fileno()).st_size

        # Avoid unreasonable allocations on corrupt or hostile images.
        if entry_count > 16384 or entry_size > 4096:
            return []

        table_offset = entry_lba * 512
        table_size = entry_count * entry_size

        if table_offset < 0 or table_offset + table_size > image_size:
            return []

        table = self._read_at(table_offset, table_size)

        if len(table) != table_size:
            return []

        partitions = []

        for index in range(entry_count):
            entry = table[index * entry_size:(index + 1) * entry_size]

            # An all-zero type GUID means this GPT entry is unused.
            if entry[:16] == b"\x00" * 16:
                continue

            first_lba = struct.unpack_from("<Q", entry, 32)[0]
            last_lba = struct.unpack_from("<Q", entry, 40)[0]

            if last_lba < first_lba:
                continue

            partitions.append({
                "scheme": "GPT",
                "partition_number": index + 1,
                "type_guid": str(
                    __import__("uuid").UUID(bytes_le=entry[:16])
                ),
                "start_lba": first_lba,
                "end_lba": last_lba,
                "sector_size": 512,
                "start_offset": first_lba * 512,
                "size_bytes": (last_lba - first_lba + 1) * 512,
            })

        return partitions

    def _select_ntfs_volume(self):
        # Case 1: a standalone NTFS volume begins at byte zero.
        direct_info = self._valid_ntfs_boot_sector(0)

        if direct_info:
            self.partition_info = {
                "scheme": "RAW",
                "partition_number": None,
                "start_offset": 0,
                "size_bytes": direct_info["volume_size_bytes"],
            }
            return direct_info

        # Case 2: GPT disk image.
        gpt_partitions = self._read_gpt_partitions()

        # Case 3: MBR disk image, if it is not GPT.
        partitions = (
            gpt_partitions
            if gpt_partitions
            else self._read_mbr_partitions()
        )

        image_size = os.fstat(self.image.fileno()).st_size

        for partition in partitions:
            offset = partition["start_offset"]
            partition_size = partition["size_bytes"]

            if (
                offset < 0
                or partition_size <= 0
                or offset + partition_size > image_size
            ):
                continue

            info = self._valid_ntfs_boot_sector(offset)

            if not info:
                continue

            # The NTFS volume must also fit inside the partition boundary.
            if info["volume_size_bytes"] > partition_size:
                continue

            self.partition_info = partition
            return info

        raise ValueError(
            "No supported NTFS volume found. The image may use an "
            "unsupported filesystem, an unsupported partition layout, "
            "or contain invalid partition metadata."
        )

    def detect_filesystem(self, image=None):
        if image is not None:
            self.image = image

        info = self._select_ntfs_volume()
        self.filesystem = "NTFS"
        self.volume_offset = info["volume_offset"]
        return self.filesystem

    def create_parser(self, image=None):
        if image is not None:
            self.image = image

        info = self._select_ntfs_volume()
        self.filesystem = "NTFS"
        self.volume_offset = info["volume_offset"]

        parser = NTFSParser(
            self.image,
            self.repository,
            self.case_id,
            volume_offset=self.volume_offset,
        )

        # Keep detected partition metadata available to the engine/UI.
        parser.partition_info = self.partition_info
        parser.detected_boot_info = info

        return parser
