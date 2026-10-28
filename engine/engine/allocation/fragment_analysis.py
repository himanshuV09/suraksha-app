from dataclasses import dataclass

from engine.allocation.recovery_fragment import RecoveryFragment


@dataclass(frozen=True)
class FragmentAnalysis:
    """
    Describes the physical fragments associated with a recovery
    candidate.

    This is an analysis result only.

    It does NOT:
        - read image data
        - recover data
        - write files
        - create evidence objects
    """

    fragments: list
    complete: bool

    def __post_init__(self):
        if not isinstance(self.fragments, list):
            raise TypeError(
                "fragments must be a list"
            )

        for fragment in self.fragments:
            if not isinstance(
                fragment,
                RecoveryFragment,
            ):
                raise TypeError(
                    "fragments must contain only "
                    "RecoveryFragment objects"
                )

        if not isinstance(self.complete, bool):
            raise TypeError(
                "complete must be a boolean"
            )


        expected_sequences = list(
            range(len(self.fragments))
        )

        actual_sequences = [
            fragment.sequence
            for fragment in self.fragments
        ]

        if actual_sequences != expected_sequences:
            raise ValueError(
                "fragment sequences must be "
                "ordered and contiguous"
            )