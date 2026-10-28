from recovery import (
    recover_resident_data,
    recover_non_resident_data,
)


class RecoveryService:

    def recover(
        self,
        image_reader,
        evidence
    ):

        if evidence.record_type == "Resident":

            return recover_resident_data(
                evidence
            )

        return recover_non_resident_data(
            image_reader,
            evidence
        )