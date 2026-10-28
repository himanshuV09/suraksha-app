from engine.volume.geometry import VolumeGeometry

from recovery import (
    recover_resident_data,
)


class ImageReader:
    """Reads NTFS clusters (addressed by LCN) from a disk image."""

    def __init__(
        self,
        image,
        cluster_size,
        volume_offset=0,
    ):
        self.image = image
        self.geometry = VolumeGeometry(
            volume_offset=volume_offset,
            cluster_size=cluster_size,
        )

    @classmethod
    def for_parser(cls, parser):
        """Build a reader that uses the parser's detected volume location."""
        return cls(
            parser.image_handle,
            parser.cluster_size,
            volume_offset=parser.volume_offset,
        )

    @property
    def cluster_size(self):
        return self.geometry.cluster_size

    def read_clusters(
        self,
        lcn,
        length
    ):
        self.image.seek(self.geometry.cluster_offset(lcn))

        return self.image.read(length * self.cluster_size)

    def read(
        self,
        evidence
    ):
        if evidence.record_type == "Resident":
            return recover_resident_data(evidence)

        raise NotImplementedError(
            "Use RecoveryService.recover() for non-resident files."
        )
