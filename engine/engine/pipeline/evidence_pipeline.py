from pathlib import Path

class EvidencePipeline:

    def __init__(

        self,

    ):

        self.stages =  []

    def add_stage(

        self,

        stage

    ):

        self.stages.append(stage)

    def execute(

        self,

        evidence_objects,

        context

    ):

        # for stage in self.stages:

        #     stage.process(evidence_objects,context)

        log = Path("pipeline.log")

        with log.open("a", encoding="utf-8") as f:

            f.write(f"Pipeline stages: {len(self.stages)}\n")

            for stage in self.stages:

                f.write(f"Running {stage.__class__.__name__}\n")

                stage.process(
                    evidence_objects,
                    context
                )