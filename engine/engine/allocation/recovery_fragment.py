from dataclasses import dataclass


@dataclass(frozen=True)
class RecoveryFragment:
    """
    Describes one physical byte range belonging to a
    recovery operation.

    This is a recovery description only.

    It does NOT:
        - read image data
        - carve data
        - write recovered files
    """

    source_offset: int
    size: int
    sequence: int

    def __post_init__(self):
        if not isinstance(self.source_offset, int):
            raise TypeError(
                "source_offset must be an integer"
            )

        if self.source_offset < 0:
            raise ValueError(
                "source_offset cannot be negative"
            )

        if not isinstance(self.size, int):
            raise TypeError(
                "size must be an integer"
            )

        if self.size <= 0:
            raise ValueError(
                "size must be greater than zero"
            )

        if not isinstance(self.sequence, int):
            raise TypeError(
                "sequence must be an integer"
            )

        if self.sequence < 0:
            raise ValueError(
                "sequence cannot be negative"
            )