from engine.recovery.image_reader import ImageReader
from engine.volume.opener import open_ntfs_volume


class PreviewSession:
    """Opens an evidence image just long enough to preview one record."""

    def __init__(self, image_path):

        self.image_path = image_path
        self.image = None
        self.parser = None
        self.image_reader = None

    def open(self):

        self.image = open(
            self.image_path,
            "rb"
        )

        self.parser = open_ntfs_volume(self.image)

        self.image_reader = ImageReader.for_parser(self.parser)

    def get_evidence(
        self,
        record_number
    ):

        return self.parser.get_evidence(
            record_number
        )

    def close(self):

        if self.image:

            self.image.close()
