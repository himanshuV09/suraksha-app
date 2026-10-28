import io

from engine.allocation.carved_artifact import CarvedArtifact
from engine.allocation.carving_models import SignatureCandidate
from engine.allocation.unallocated_recovery_workflow import (
    UnallocatedRecoveryWorkflow,
)
from engine.allocation.unallocated_region_service import UnallocatedRegion
from engine.allocation.validated_candidate import ValidatedCandidate

import hashlib

from engine.allocation.recovery_result import (
    RecoveryResult,
    RecoveryStatus,
)



def make_candidate():
    return SignatureCandidate(
        signature="JPEG",
        extension=".jpg",
        offset=4096,
        relative_offset=0,
        start_cluster=1,
        end_cluster=1,
        confidence=0.95,
    )


def make_validated_candidate():
    return ValidatedCandidate(
        candidate=make_candidate(),
        detected_size=8,
        validation_reason="JPEG structural validation passed",
    )


class FakeRecoveryService:
    def recover(self, candidate):
        artifact = CarvedArtifact(
            candidate=candidate,
            data=(
                b"\xff\xd8\xff\xe0"
                b"\x00\x10"
                b"\xff\xd9"
            ),
            source_offset=candidate.offset,
            size=candidate.detected_size,
        )

        return RecoveryResult(
            status=RecoveryStatus.RECOVERED,
            artifact=artifact,
            reason="Candidate recovered successfully",
        )


def make_region():
    return UnallocatedRegion(
        start_cluster=1,
        end_cluster=1,
        cluster_count=1,
        start_offset=4096,
        end_offset=8192,
        byte_count=4096,
    )


def test_workflow_recovers_validated_candidate():
    image = io.BytesIO(
        b"\x00" * 4096
        + b"\xff\xd8\xff\xe0\x00\x10\xff\xd9"
        + b"\x00" * 4088
    )

    workflow = UnallocatedRecoveryWorkflow(
        recovery_service=FakeRecoveryService(),
    )

    candidate = make_validated_candidate()
    region = make_region()

    result = workflow.recover(
        image=image,
        region=region,
        candidate=candidate,
        source_image="test.001",
    )

    assert result.artifact.signature == "JPEG"
    assert result.artifact.extension == ".jpg"
    assert result.artifact.source_offset == 4096
    assert result.artifact.size == 8

    assert result.sha256 == hashlib.sha256(result.artifact.data).hexdigest()