from engine import progress
from engine.allocation.unallocated_scanner import UnallocatedScanner
from engine.allocation.signature_detector import SignatureDetector
from engine.allocation.carving_models import SignatureCandidate
from engine.allocation.signature_validator import (
    SignatureValidator,
)

from engine.allocation.candidate_context_factory import (
    CandidateContextFactory,
)

from engine.allocation.unallocated_candidate_context import (
    UnallocatedCandidateContext,
)

from engine.allocation.validated_candidate import (
    ValidatedCandidate,
)

# Formats whose bytes contain other files' signatures.
CONTAINER_SIGNATURES = {"ZIP", "PDF", "GZIP"}


class UnallocatedSignatureService:
    """
    Detect file-signature candidates inside NTFS unallocated space.

    Pipeline:

        UnallocatedReader
                ↓
        UnallocatedScanner
                ↓
        SignatureDetector
                ↓
        SignatureCandidate

    This service does NOT:

        - carve files
        - validate files
        - determine file length
        - reconstruct fragmented files
        - write recovered files
        - create database evidence objects

    A SignatureCandidate represents only a possible file signature.
    """

    def __init__(
        self,
        reader,
        window_size=64 * 1024,
    ):
        if reader is None:
            raise ValueError(
                "reader cannot be None"
            )

       
        if (
            not isinstance(window_size, int)
            or isinstance(window_size, bool)
        ):
            raise TypeError(
                "window_size must be an integer"
            )

        if window_size <= 0:
            raise ValueError(
                "window_size must be positive"
            )

        self.reader = reader
        self.window_size = window_size
        self.detector = SignatureDetector()
        self.validator = SignatureValidator()

        self.context_factory = None

    def scan(self):
        """
        Scan unallocated space and return signature candidates.

        Returns:
            list[SignatureCandidate]
        """

        scanner = UnallocatedScanner(
            reader=self.reader,
            window_size=self.window_size,
            overlap_size=min(8, self.window_size - 1),
        )

        candidates = []
        seen = set()

        for window in scanner.scan():

            detected = self.detector.detect(
                window["data"],
                window["offset"],
            )

            for candidate in detected:
                identity = (candidate.signature, candidate.offset)
                if identity in seen:
                    continue
                seen.add(identity)

                candidates.append(
                    SignatureCandidate(
                        signature=candidate.signature,
                        extension=candidate.extension,
                        offset=candidate.offset,
                        relative_offset=candidate.relative_offset,
                        start_cluster=None,
                        end_cluster=None,
                        confidence=candidate.confidence,
                        metadata={
                            **candidate.metadata,
                            "source": "UNALLOCATED",
                            "scan_window_start_cluster": window.get(
                                "start_cluster"
                            ),
                            "scan_window_end_cluster": window.get(
                                "end_cluster"
                            ),
                        },
                    )
                )

        return candidates

    def scan_validated(
        self,
        contexts,
    ):
        """
        Validate candidate contexts and return only
        structurally validated candidates.

        Invalid candidates are rejected.

        Returns:
            list[ValidatedCandidate]
        """

        if not isinstance(contexts, list):
            raise TypeError(
                "contexts must be a list"
            )

        validated_candidates = []

        for context in contexts:

            if not isinstance(
                context,
                UnallocatedCandidateContext,
            ):
                raise TypeError(
                    "contexts must contain only "
                    "UnallocatedCandidateContext objects"
                )

            validated = (
                self.validator.to_validated_candidate(
                    context
                )
            )

            if validated is not None:
                validated_candidates.append(
                    validated
                )

        return validated_candidates

    def configure_candidate_context_factory(
        self,
        image,
        regions,
    ):
        """
        Configure the factory used to create safe
        UnallocatedCandidateContext objects.

        The factory resolves each candidate against
        the supplied unallocated regions before creating
        its context.

        This method does NOT:

            - validate file structure
            - carve files
            - modify the forensic image
        """

        self.context_factory = CandidateContextFactory(
            image=image,
            regions=regions,
        )

    def scan_and_validate_candidates(
        self,
        candidates,
    ):
        """
        Resolve and validate signature candidates.

        Pipeline:

            SignatureCandidate
                    ↓
            CandidateContextFactory
                    ↓
            UnallocatedCandidateContext
                    ↓
            SignatureValidator
                    ↓
            ValidatedCandidate

        Candidates that cannot be resolved to an
        unallocated region are rejected.

        Returns:
            list[ValidatedCandidate]
        """

        if not isinstance(candidates, list):
            raise TypeError(
                "candidates must be a list"
            )

        if self.context_factory is None:
            raise RuntimeError(
                "Candidate context factory "
                "has not been configured"
            )

        validated_candidates = []
        # End offset of the last validated container. A signature inside it
        # is part of that file (a ZIP member, an image inside a PDF), not a
        # separate file, so it is skipped rather than carved twice.
        covered_until = -1
        self.nested_skipped = 0

        ordered = sorted(candidates, key=lambda item: item.offset)
        for index, candidate in enumerate(ordered, start=1):
            progress.report("Validating signature matches", index, len(ordered))
            if candidate.offset < covered_until:
                self.nested_skipped += 1
                continue

            if not isinstance(
                candidate,
                SignatureCandidate,
            ):
                raise TypeError(
                    "candidates must contain only "
                    "SignatureCandidate objects"
                )

            try:
                context = (
                    self.context_factory.create(
                        candidate
                    )
                )

            except LookupError:
                # Candidate does not belong to an
                # unallocated region.
                continue

            validated = (
                self.validator.to_validated_candidate(
                    context
                )
            )

            if validated is not None:
                validated_candidates.append(
                    validated
                )
                # Only containers swallow what is inside them. A JPEG's
                # embedded thumbnail is still carved: it can survive edits
                # to the main picture.
                if validated.candidate.signature in CONTAINER_SIGNATURES:
                    covered_until = max(
                        covered_until,
                        validated.offset + validated.detected_size,
                    )

        return validated_candidates