from engine.volume.run_stream import RunStream

from .zip_parser import ZipParser


class ContainerManager:
    """Lists the members of container files (ZIP, Office documents, ...)."""

    def __init__(self):

        self.parsers = [
            ZipParser(),
        ]

    def analyze(self, evidence, context):

        if evidence.directory or not evidence.file_size:
            return []

        # Decide by name first: reading a file only to discard it was the
        # single largest cost of the whole analysis.
        parser = next(
            (parser for parser in self.parsers if parser.supports(evidence)),
            None,
        )
        if parser is None:
            return []

        reader = context.image_reader
        stream = RunStream.for_evidence(reader.image, reader.geometry, evidence)

        return parser.parse(evidence, stream)
