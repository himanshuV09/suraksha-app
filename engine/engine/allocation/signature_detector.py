from engine.allocation.carving_models import SignatureCandidate

class SignatureDetector:
    """
    Detect known file signatures inside unallocated-space
    scan windows.

    This class only identifies candidates.

    It does NOT:
        - carve files
        - determine file size
        - validate files
        - write files to disk
        - create evidence objects
    """

    SIGNATURES = [
        {
            "name": "JPEG",
            "extension": ".jpg",
            "signature": b"\xFF\xD8\xFF",
        },
        {
            "name": "PNG",
            "extension": ".png",
            "signature": b"\x89PNG\r\n\x1a\n",
        },
        {
            "name": "GIF",
            "extension": ".gif",
            "signature": b"GIF8",
        },
        {
            "name": "PDF",
            "extension": ".pdf",
            "signature": b"%PDF-",
        },
        {
            "name": "ZIP",
            "extension": ".zip",
            "signature": b"PK\x03\x04",
        },
        {
            "name": "OLE",
            "extension": ".ole",
            "signature": b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1",
        },
        {
            "name": "RAR",
            "extension": ".rar",
            "signature": b"Rar!\x1A\x07",
        },
        {
            "name": "GZIP",
            "extension": ".gz",
            # ID1 ID2 plus CM=8 (deflate, the only defined method). The bare
            # 2-byte magic matched random data thousands of times per GB.
            "signature": b"\x1F\x8B\x08",
        },
    ]

    def detect(self, data, base_offset):
        """
        Detect signatures inside a byte buffer.

        Returns a list of candidates.

        Each candidate contains:

            {
                "signature": str,
                "extension": str,
                "offset": int,
                "relative_offset": int
            }
        """

        if not isinstance(data, bytes):
            raise TypeError("data must be bytes")

        if base_offset < 0:
            raise ValueError("base_offset must be non-negative")

        candidates = []

        for signature_info in self.SIGNATURES:

            signature = signature_info["signature"]

            search_position = 0

            while True:

                position = data.find(
                    signature,
                    search_position
                )

                if position == -1:
                    break

                candidates.append(
                    SignatureCandidate(
                        signature=signature_info["name"],
                        extension=signature_info["extension"],
                        offset=base_offset + position,
                        relative_offset=position,
                        confidence=0.50,
                    )
                )

                search_position = position + 1

        candidates.sort(
            key=lambda candidate: candidate.offset
        )

        return candidates