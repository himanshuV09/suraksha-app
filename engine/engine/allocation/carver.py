from engine.allocation.carved_artifact import CarvedArtifact
from engine.allocation.carving_reader import CarvingReader
from engine.allocation.recovery_plan import RecoveryPlan


class Carver:
    """
    Recovers bytes described by a RecoveryPlan.

    The Carver does not:
        - detect signatures
        - validate candidates
        - determine file size
        - analyze filesystem allocation
        - write recovered files
        - create database records

    Those responsibilities belong to other layers.
    """

    def __init__(self, reader):
        if reader is None:
            raise ValueError("reader cannot be None")

        if not isinstance(reader, CarvingReader):
            raise TypeError(
                "reader must be a CarvingReader"
            )

        self.reader = reader

    def carve(self, plan):
        if not isinstance(plan, RecoveryPlan):
            raise TypeError(
                "plan must be a RecoveryPlan"
            )

        data = self.reader.read(plan)

        return CarvedArtifact(
            candidate=plan.candidate,
            data=data,
            source_offset=plan.source_offset,
            size=len(data),
        )