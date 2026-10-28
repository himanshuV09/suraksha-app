from abc import ABC, abstractmethod


class PipelineStage(ABC):

    @abstractmethod
    def process(

        self,

        evidence_objects,

        context

    ):

        pass