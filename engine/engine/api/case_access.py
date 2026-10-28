"""Checks shared by APIs that read the evidence image of a case."""
import os

from engine.errors import EvidenceMismatchError, NotFoundError


def validate_case_image(repository, case_id, image_path):
    """Verify that ``image_path`` is the image registered to ``case_id``."""
    case = repository.get_case(case_id)

    if case is None:
        raise NotFoundError(f"Case {case_id} was not found in the database")

    registered_image_path = case[2]  # cases.image_path

    if not registered_image_path:
        raise NotFoundError(f"Case {case_id} has no registered evidence image")

    expected = os.path.normcase(os.path.abspath(registered_image_path))
    supplied = os.path.normcase(os.path.abspath(image_path))

    if expected != supplied:
        raise EvidenceMismatchError(
            "The selected image does not match the image registered "
            f"to case {case_id}"
        )
