"""Application service that scans and persists validated unallocated artifacts.

This is deliberately invoked as a separate command instead of being run
implicitly during ordinary MFT analysis: carving can be expensive on large images.
"""
from collections import Counter

from database.recovered_artifact_repository import RecoveredArtifactRepository
from engine.allocation.candidate_extent_analyzer import CandidateExtentAnalyzer
from engine.allocation.carver import Carver
from engine.allocation.carving_reader import CarvingReader
from engine.allocation.fragment_analyzer import FragmentAnalyzer
from engine.allocation.fragmented_recovery import recover_fragmented
from engine.allocation.recovery_planner import RecoveryPlanner
from engine.allocation.unallocated_carving_service import UnallocatedCarvingService
from engine.allocation.unallocated_reader import UnallocatedReader
from engine.allocation.unallocated_recovery_workflow import UnallocatedRecoveryWorkflow
from engine.allocation.unallocated_signature_service import UnallocatedSignatureService


class UnallocatedRecoveryApplication:
    """Run the complete detection-to-persistence workflow for one case image."""

    def __init__(self, chunk_size=1024 * 1024, window_size=64 * 1024):
        if not isinstance(chunk_size, int) or isinstance(chunk_size, bool) or chunk_size <= 0:
            raise ValueError("chunk_size must be a positive integer")
        if not isinstance(window_size, int) or isinstance(window_size, bool) or window_size <= 0:
            raise ValueError("window_size must be a positive integer")
        self.chunk_size = chunk_size
        self.window_size = window_size

    def run(self, image, parser, database, case_id, source_image):
        if image is None:
            raise ValueError("image cannot be None")
        if parser is None:
            raise ValueError("parser cannot be None")
        if database is None or database.cursor is None:
            raise ValueError("database must be open")
        if not isinstance(case_id, int) or isinstance(case_id, bool) or case_id <= 0:
            raise ValueError("case_id must be a positive integer")
        if not isinstance(source_image, str) or not source_image.strip():
            raise ValueError("source_image cannot be empty")

        database.cursor.execute(
            "SELECT 1 FROM cases WHERE case_id = ?",
            (case_id,),
        )
        if database.cursor.fetchone() is None:
            raise ValueError(
                f"case_id {case_id} does not exist in the selected database"
            )

        regions = parser.get_unallocated_regions()
        allocation_ranges = parser.allocation_ranges
        cluster_size = parser.cluster_size
        # Where the NTFS volume starts inside the image (0 for a bare
        # volume). Needed to turn image offsets into cluster numbers.
        volume_offset = getattr(parser, "volume_offset", 0)
        reader = UnallocatedReader(
            image=image,
            ranges=regions,
            cluster_size=cluster_size,
            chunk_size=self.chunk_size,
        )
        signature_service = UnallocatedSignatureService(
            reader=reader,
            window_size=self.window_size,
        )
        signature_service.configure_candidate_context_factory(
            image=image,
            regions=regions,
        )
        context_factory = signature_service.context_factory

        # Scan all unallocated ranges. Signature hits are not treated as
        # recoveries until structural validation and extent checks both pass.
        candidates = signature_service.scan()
        validated_candidates = signature_service.scan_and_validate_candidates(candidates)

        extent_analyzer = CandidateExtentAnalyzer(
            allocation_ranges=allocation_ranges,
            cluster_size=cluster_size,
            volume_offset=volume_offset,
        )
        carving_service = UnallocatedCarvingService(
            extent_analyzer=extent_analyzer,
            fragment_analyzer=FragmentAnalyzer(
                cluster_size=cluster_size,
                volume_offset=volume_offset,
            ),
            recovery_planner=RecoveryPlanner(),
            carver=Carver(CarvingReader(image)),
        )
        workflow = UnallocatedRecoveryWorkflow(carving_service)
        repository = RecoveredArtifactRepository(database)

        status_counts = Counter()
        persisted = []
        per_candidate_errors = 0
        existing_offsets = {
            record.source_offset
            for record in repository.list_by_case(case_id)
        }

        for candidate in validated_candidates:
            if candidate.offset in existing_offsets:
                status_counts["ALREADY_PERSISTED"] += 1
                continue
            try:
                context = context_factory.create(candidate.candidate)
                result = workflow.recover_and_persist(
                    image=image,
                    region=context.region,
                    candidate=candidate,
                    source_image=source_image,
                    case_id=case_id,
                    repository=repository,
                )
                status_counts[result.recovery.status.value] += 1
                if result.artifact_id is not None:
                    existing_offsets.add(candidate.offset)
                    persisted.append({
                        "artifact_id": result.artifact_id,
                        "signature": result.artifact.signature,
                        "extension": result.artifact.extension,
                        "size": result.artifact.size,
                        "sha256": result.sha256,
                        "source_offset": result.artifact.source_offset,
                    })
            except (LookupError, ValueError, TypeError, OSError):
                # A bad candidate must not abort the entire scan. The count is
                # reported so rejected candidates are not silently hidden.
                per_candidate_errors += 1

        # Second pass: files that continue after an allocated block.
        fragmented, retried = recover_fragmented(
            image=image,
            regions=regions,
            candidates=candidates,
            validated=validated_candidates,
            context_factory=context_factory,
            repository=repository,
            case_id=case_id,
            source_image=source_image,
            cluster_size=cluster_size,
            volume_offset=volume_offset,
            existing_offsets=existing_offsets,
        )
        if fragmented:
            status_counts["RECOVERED_FRAGMENTED"] += len(fragmented)
        persisted += fragmented

        return {
            "success": True,
            "case_id": case_id,
            "image_path": source_image,
            "unallocated_regions": len(regions),
            "candidates_detected": len(candidates),
            "candidates_validated": len(validated_candidates),
            # Signatures inside an already validated file (ZIP members,
            # JPEG thumbnails) are part of that file, not separate files.
            "candidates_nested": getattr(signature_service, "nested_skipped", 0),
            "recovered_count": len(persisted),
            "recovered_fragmented": len(fragmented),
            "fragment_retries": retried,
            "recovered_by_type": dict(Counter(item["extension"] for item in persisted)),
            "candidate_errors": per_candidate_errors,
            "recovery_status_counts": dict(status_counts),
            "artifacts": persisted,
            "supported_structural_validation": ["JPEG", "PNG", "GIF", "PDF", "ZIP", "GZIP"],
            "note": (
                "OLE (legacy Office) and RAR signatures are detected but not yet "
                "validated, so they are not carved. Files larger than 64 MiB are "
                "not carved. Fragmented files are reassembled only for PNG, ZIP, "
                "GZIP and PDF (formats with integrity checks), up to 16 MiB, "
                "following free space past allocated blocks."
            ),
        }
