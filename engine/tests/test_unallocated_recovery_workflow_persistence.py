import hashlib
import io

from engine.allocation.allocation_models import UnallocatedRegion
from engine.allocation.candidate_extent_analyzer import CandidateExtentAnalyzer
from engine.allocation.carver import Carver
from engine.allocation.carving_models import SignatureCandidate
from engine.allocation.carving_reader import CarvingReader
from engine.allocation.fragment_analyzer import FragmentAnalyzer
from engine.allocation.recovery_planner import RecoveryPlanner
from engine.allocation.recovery_result import RecoveryStatus
from engine.allocation.unallocated_carving_service import UnallocatedCarvingService
from engine.allocation.unallocated_recovery_workflow import UnallocatedRecoveryWorkflow
from engine.allocation.validated_candidate import ValidatedCandidate


def test_successful_recovery_is_assembled_and_persisted():
    image_bytes = b"\x00" * 4096 + b"\xff\xd8\xff\x01\x02\xff\xd9" + b"\x00" * 4088
    image = io.BytesIO(image_bytes)
    region = UnallocatedRegion(
        start_cluster=1,
        end_cluster=1,
        cluster_count=1,
        start_offset=4096,
        end_offset=8192,
        byte_count=4096,
    )
    signature = SignatureCandidate(
        signature="JPEG",
        extension=".jpg",
        offset=4096,
        relative_offset=0,
        start_cluster=1,
        end_cluster=1,
        confidence=0.95,
    )
    candidate = ValidatedCandidate(
        candidate=signature,
        detected_size=7,
        validation_reason="JPEG structural validation passed",
    )
    ranges = [
        {"start_cluster": 0, "end_cluster": 0, "cluster_count": 1, "state": "allocated"},
        {"start_cluster": 1, "end_cluster": 1, "cluster_count": 1, "state": "unallocated"},
    ]
    extent_analyzer = CandidateExtentAnalyzer(ranges, cluster_size=4096)
    service = UnallocatedCarvingService(
        extent_analyzer=extent_analyzer,
        fragment_analyzer=FragmentAnalyzer(cluster_size=4096),
        recovery_planner=RecoveryPlanner(),
        carver=Carver(CarvingReader(image)),
    )

    class Repository:
        record = None

        def create(self, case_id, record):
            assert case_id == 42
            self.record = record
            return 123

    repository = Repository()
    result = UnallocatedRecoveryWorkflow(service).recover_and_persist(
        image=image,
        region=region,
        candidate=candidate,
        source_image="test.001",
        case_id=42,
        repository=repository,
    )

    assert result.recovery.status == RecoveryStatus.RECOVERED
    assert result.artifact_id == 123
    assert result.sha256 == hashlib.sha256(result.artifact.data).hexdigest()
    assert repository.record.sha256 == result.sha256
    assert repository.record.provenance.source_image == "test.001"
    assert repository.record.provenance.relative_offset == 0


def test_candidate_extent_must_fit_inside_region_before_recovery():
    region = UnallocatedRegion(
        start_cluster=1,
        end_cluster=1,
        cluster_count=1,
        start_offset=4096,
        end_offset=8192,
        byte_count=4096,
    )
    candidate = ValidatedCandidate(
        candidate=SignatureCandidate(
            signature="JPEG", extension=".jpg", offset=8190,
            relative_offset=0, start_cluster=1, end_cluster=1,
            confidence=0.95,
        ),
        detected_size=4,
        validation_reason="test candidate",
    )

    class NeverCalled:
        def recover(self, candidate):
            raise AssertionError("recovery must not run for out-of-bounds candidate")

    import pytest
    with pytest.raises(ValueError, match="candidate extent exceeds"):
        UnallocatedRecoveryWorkflow(NeverCalled()).recover_and_persist(
            image=io.BytesIO(b"\x00" * 8192),
            region=region,
            candidate=candidate,
            source_image="test.001",
            case_id=1,
            repository=object(),
        )
