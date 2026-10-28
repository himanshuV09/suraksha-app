import hashlib

from engine.allocation.carved_artifact import CarvedArtifact


class ArtifactHasher:
    """Computes cryptographic hashes for recovered carved artifacts."""

    def sha256(self, artifact: CarvedArtifact) -> str:
        if not isinstance(artifact, CarvedArtifact):
            raise TypeError("artifact must be a CarvedArtifact")

        return hashlib.sha256(artifact.data).hexdigest()