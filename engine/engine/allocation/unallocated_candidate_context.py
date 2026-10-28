from engine.allocation.allocation_models import UnallocatedRegion
from engine.allocation.carving_models import SignatureCandidate


class UnallocatedCandidateContext:
    """
    Provides controlled access to the unallocated region containing
    a signature candidate.

    This class connects:

        UnallocatedRegion
                ↓
        SignatureCandidate
                ↓
        bounded candidate reads

    It does NOT:

        - validate the file
        - determine file size
        - carve the file
        - write recovered files
        - modify the forensic image
    """

    def __init__(
        self,
        image,
        region,
        candidate,
    ):
        if image is None:
            raise ValueError(
                "image cannot be None"
            )

        if not isinstance(
            region,
            UnallocatedRegion
        ):
            raise TypeError(
                "region must be an UnallocatedRegion"
            )

        if not isinstance(
            candidate,
            SignatureCandidate
        ):
            raise TypeError(
                "candidate must be a SignatureCandidate"
            )

        if candidate.offset < region.start_offset:
            raise ValueError(
                "candidate offset is before the unallocated region"
            )

        if candidate.offset >= region.end_offset:
            raise ValueError(
                "candidate offset is outside the unallocated region"
            )

        self.image = image
        self.region = region
        self.candidate = candidate

    @property
    def absolute_offset(self):
        """
        Absolute image offset where the candidate signature begins.
        """

        return self.candidate.offset

    @property
    def relative_offset(self):
        """
        Offset of the candidate relative to the beginning
        of its unallocated region.
        """

        return (
            self.candidate.offset
            - self.region.start_offset
        )

    @property
    def remaining_bytes(self):
        """
        Number of bytes available from the candidate offset
        until the end of the unallocated region.
        """

        return (
            self.region.end_offset
            - self.candidate.offset
        )

    def read(self, size, relative_offset=0):
        """
        Read bytes starting at the candidate offset.

        The read is strictly bounded by the containing
        unallocated region.
        """

        if not isinstance(size, int) or isinstance(size, bool):
            raise TypeError(
                "size must be an integer"
            )

        if not isinstance(relative_offset, int) or isinstance(relative_offset, bool):
            raise TypeError("relative_offset must be an integer")

        if relative_offset < 0:
            raise ValueError("relative_offset cannot be negative")

        if size <= 0:
            raise ValueError(
                "size must be greater than zero"
            )

        if relative_offset + size > self.remaining_bytes:
            raise ValueError(
                "requested read exceeds "
                "the containing unallocated region"
            )

        self.image.seek(
            self.candidate.offset + relative_offset
        )

        data = self.image.read(size)

        if len(data) != size:
            raise IOError(
                "Unable to completely read "
                "candidate data"
            )

        return data