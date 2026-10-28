from dataclasses import dataclass


@dataclass(frozen=True)
class ArtifactProvenance:
    """Immutable forensic provenance for a recovered artifact."""

    source_image: str
    source_type: str
    region_start_cluster: int
    region_end_cluster: int
    region_start_offset: int
    source_offset: int
    relative_offset: int
    start_cluster: int
    end_cluster: int

    def __post_init__(self):
        if not isinstance(self.source_image, str):
            raise TypeError("source_image must be a string")

        if not self.source_image.strip():
            raise ValueError("source_image cannot be empty")

        if not isinstance(self.source_type, str):
            raise TypeError("source_type must be a string")

        if not self.source_type.strip():
            raise ValueError("source_type cannot be empty")

        integer_fields = (
            "region_start_cluster",
            "region_end_cluster",
            "region_start_offset",
            "source_offset",
            "relative_offset",
            "start_cluster",
            "end_cluster",
        )

        for field_name in integer_fields:
            value = getattr(self, field_name)

            if not isinstance(value, int):
                raise TypeError(f"{field_name} must be an integer")

            if value < 0:
                raise ValueError(f"{field_name} cannot be negative")

        if self.region_end_cluster < self.region_start_cluster:
            raise ValueError(
                "region_end_cluster cannot be before region_start_cluster"
            )

        if self.end_cluster < self.start_cluster:
            raise ValueError(
                "end_cluster cannot be before start_cluster"
            )

        if self.start_cluster < self.region_start_cluster:
            raise ValueError(
                "start_cluster cannot be before region_start_cluster"
            )

        if self.end_cluster > self.region_end_cluster:
            raise ValueError(
                "end_cluster cannot be after region_end_cluster"
            )

        expected_relative_offset = (
            self.source_offset
            - self.region_start_offset
        )

        if expected_relative_offset != self.relative_offset:
            raise ValueError(
                "relative_offset is inconsistent with source_offset"
            )