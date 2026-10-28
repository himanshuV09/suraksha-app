from ..base_stage import PipelineStage

from ...container.manager import ContainerManager


class ContainerStage(PipelineStage):
    """Lists members of container files and stores them in one batch."""

    def __init__(self):

        self.manager = ContainerManager()

    def process(

        self,

        evidence_objects,

        context

    ):

        found = []

        for evidence in evidence_objects:

            artifacts = self.manager.analyze(

                evidence,

                context

            )

            # Kept in memory for later stages.
            evidence.children = artifacts

            found += [(evidence.record_number, artifact) for artifact in artifacts]

        context.repository.insert_container_artifacts(

            context.case.case_id,

            found

        )
