from abc import ABC, abstractmethod


class BaseContainerParser(ABC):

    @abstractmethod
    def supports(self, evidence):
        """
        Return True if this parser can handle the evidence.
        """
        pass

    @abstractmethod
    def parse(self, evidence, source):
        """
        Return a list of virtual child artifacts.

        ``source`` is a seekable file object over the evidence's data.
        """
        pass