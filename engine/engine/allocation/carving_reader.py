from engine.allocation.recovery_plan import RecoveryPlan


class CarvingReader:
    """
    Reads exactly the bytes permitted by a RecoveryPlan.

    This reader operates using absolute byte offsets.
    It is separate from the filesystem/MFT ImageReader,
    which operates using LCN/data runs.
    """

    def __init__(self, image):
        if image is None:
            raise ValueError("image cannot be None")

        self.image = image

    def read(self, plan):
        if not isinstance(plan, RecoveryPlan):
            raise TypeError(
                "plan must be a RecoveryPlan"
            )

        self.image.seek(plan.source_offset)

        data = self.image.read(plan.requested_size)

        if len(data) != plan.requested_size:
            raise IOError(
                "Unable to completely read planned recovery data"
            )

        return data