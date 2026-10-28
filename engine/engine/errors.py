"""Error types that the CLI reports to clients by name.

Anything not listed here is reported as "EngineError".
"""


class EngineError(Exception):
    """Base class for errors the engine reports deliberately."""

    error_type = "EngineError"


class UsageError(EngineError):
    """The command or its arguments were invalid."""

    error_type = "UsageError"


class NotFoundError(EngineError):
    """A case, record, region, or file does not exist."""

    error_type = "NotFoundError"


class EvidenceMismatchError(EngineError):
    """The supplied image does not belong to the selected case."""

    error_type = "EvidenceMismatchError"
