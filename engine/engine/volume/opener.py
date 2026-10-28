from engine.parser_manager import ParserManager


def open_ntfs_volume(image, repository=None, case_id=None):
    """Find the NTFS volume in an open image and parse its boot sector.

    Handles a bare NTFS volume as well as MBR and GPT partitioned disks.
    Every command that reads an image must open it through this function,
    so that all of them agree on where the volume starts.

    Returns an NTFSParser whose boot sector and $MFT geometry are loaded.
    """
    parser = ParserManager(image, repository, case_id).create_parser(image)
    parser.parse_boot_sector()
    return parser
