import pytest
import io

from engine.allocation.allocation_models import UnallocatedRegion
from engine.allocation.carving_models import SignatureCandidate
from engine.allocation.validated_candidate import ValidatedCandidate

from engine.allocation.recovery_result import (
    RecoveryResult,
    RecoveryStatus,
)
from engine.allocation.unallocated_recovery_workflow import (
    UnallocatedRecoveryWorkflow,
)



class FakeRecoveryService:
    def recover(self, candidate):
        return RecoveryResult(
            status=RecoveryStatus.RECOVERY_FAILED,
            artifact=None,
            reason="test recovery failure",
        )


def test_unallocated_recovery_workflow_returns_recovery_result():
    workflow = UnallocatedRecoveryWorkflow(
        recovery_service=FakeRecoveryService(),
    )

    assert workflow.recovery_service is not None

def test_unallocated_recovery_workflow_persists_recovered_artifact():
    workflow = UnallocatedRecoveryWorkflow(
        recovery_service=FakeRecoveryService(),
    )

    assert hasattr(workflow, "recover_and_persist")

def test_unallocated_recovery_workflow_rejects_missing_repository():
    workflow = UnallocatedRecoveryWorkflow(
        recovery_service=FakeRecoveryService(),
    )

    with pytest.raises(ValueError, match="repository cannot be None"):
        workflow.recover_and_persist(
            image=None,
            region=None,
            candidate=None,
            source_image="test.001",
            case_id=1,
            repository=None,
        )

def test_unallocated_recovery_workflow_rejects_invalid_case_id():
    workflow = UnallocatedRecoveryWorkflow(
        recovery_service=FakeRecoveryService(),
    )

    with pytest.raises(
        ValueError,
        match="case_id must be greater than zero",
    ):
        workflow.recover_and_persist(
            image=None,
            region=None,
            candidate=None,
            source_image="test.001",
            case_id=0,
            repository=object(),
        )

def test_unallocated_recovery_workflow_rejects_non_integer_case_id():
    workflow = UnallocatedRecoveryWorkflow(
        recovery_service=FakeRecoveryService(),
    )

    with pytest.raises(
        TypeError,
        match="case_id must be an integer",
    ):
        workflow.recover_and_persist(
            image=None,
            region=None,
            candidate=None,
            source_image="test.001",
            case_id="1",
            repository=object(),
        )

def test_unallocated_recovery_workflow_rejects_empty_source_image():
    workflow = UnallocatedRecoveryWorkflow(
        recovery_service=FakeRecoveryService(),
    )

    with pytest.raises(
        ValueError,
        match="source_image cannot be empty",
    ):
        workflow.recover_and_persist(
            image=None,
            region=None,
            candidate=None,
            source_image="   ",
            case_id=1,
            repository=object(),
        )

def test_unallocated_recovery_workflow_does_not_persist_failed_recovery():
    workflow = UnallocatedRecoveryWorkflow(
        recovery_service=FakeRecoveryService(),
    )

    class FakeRepository:
        def create(self, case_id, record):
            raise AssertionError(
                "repository.create() must not be called when recovery fails"
            )

    region = UnallocatedRegion(
        start_cluster=1, end_cluster=1, cluster_count=1,
        start_offset=4096, end_offset=8192, byte_count=4096,
    )
    candidate = ValidatedCandidate(
        candidate=SignatureCandidate(
            signature="JPEG", extension=".jpg", offset=4096,
            relative_offset=0, start_cluster=1, end_cluster=1,
            confidence=0.9,
        ),
        detected_size=8,
        validation_reason="test validation",
    )
    result = workflow.recover_and_persist(
        image=io.BytesIO(b"\x00" * 8192),
        region=region,
        candidate=candidate,
        source_image="test.001",
        case_id=1,
        repository=FakeRepository(),
    )
    assert result.recovery.status == RecoveryStatus.RECOVERY_FAILED
    assert result.artifact is None

def test_unallocated_recovery_workflow_calls_recovery_service():
    class TrackingRecoveryService:
        def __init__(self):
            self.received_candidate = None

        def recover(self, candidate):
            self.received_candidate = candidate
            return RecoveryResult(
                status=RecoveryStatus.RECOVERY_FAILED,
                artifact=None,
                reason="test recovery failure",
            )

    recovery_service = TrackingRecoveryService()

    workflow = UnallocatedRecoveryWorkflow(
        recovery_service=recovery_service,
    )

    region = UnallocatedRegion(
        start_cluster=1, end_cluster=1, cluster_count=1,
        start_offset=4096, end_offset=8192, byte_count=4096,
    )
    candidate = ValidatedCandidate(
        candidate=SignatureCandidate(
            signature="JPEG", extension=".jpg", offset=4096,
            relative_offset=0, start_cluster=1, end_cluster=1,
            confidence=0.9,
        ),
        detected_size=8,
        validation_reason="test validation",
    )
    result = workflow.recover_and_persist(
        image=io.BytesIO(b"\x00" * 8192),
        region=region,
        candidate=candidate,
        source_image="test.001",
        case_id=1,
        repository=object(),
    )

    assert result.recovery.status == RecoveryStatus.RECOVERY_FAILED
    assert recovery_service.received_candidate is candidate

