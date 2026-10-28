from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass(slots=True)
class TimelineEvent:
    """
    Represents a single forensic timeline event.

    This object is the canonical timeline model used
    throughout the investigation pipeline.
    """

    #
    # Identity
    #

    record_number: int

    filename: str

    full_path: str

    #
    # Event
    #

    timestamp: Optional[datetime]

    event_type: str

    #
    # File State
    #

    deleted: bool = False

    directory: bool = False

    #
    # Investigation
    #

    source: str = "NTFS"

    artifact_type: str = "Filesystem"

    #
    # Optional
    #

    description: str = ""

    tags: list[str] = field(default_factory=list)

    metadata: dict = field(default_factory=dict)

    #
    # --------------------------------------------------
    # Helpers
    # --------------------------------------------------
    #

    @property
    def has_timestamp(self) -> bool:
        return self.timestamp is not None

    def to_dictionary(self):

        return {

            "record_number": self.record_number,

            "filename": self.filename,

            "full_path": self.full_path,

            "timestamp":
                self.timestamp.isoformat()
                if self.timestamp
                else None,

            "event_type": self.event_type,

            "deleted": self.deleted,

            "directory": self.directory,

            "source": self.source,

            "artifact_type": self.artifact_type,

            "description": self.description,

            "tags": self.tags,

            "metadata": self.metadata,

        }