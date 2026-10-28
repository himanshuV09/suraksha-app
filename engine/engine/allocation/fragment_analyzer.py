from engine.allocation.extent_analysis import ExtentAnalysis
from engine.allocation.recovery_fragment import RecoveryFragment
from engine.allocation.fragment_analysis import FragmentAnalysis
from engine.volume.geometry import VolumeGeometry


class FragmentAnalyzer:

    """
    Converts allocation-state information into physical recovery
    fragments.

    This component does not:
        - read image data
        - validate file contents
        - carve files
        - write recovered files
    """
    def __init__(self, cluster_size, volume_offset=0):
        if not isinstance(cluster_size, int):
            raise TypeError(
                "cluster_size must be an integer"
            )

        if cluster_size <= 0:
            raise ValueError(
                "cluster_size must be positive"
            )

        # Fragments report absolute image offsets, so cluster numbers
        # must be shifted by where the volume starts in the image.
        self.geometry = VolumeGeometry(
            volume_offset=volume_offset,
            cluster_size=cluster_size,
        )
        self.cluster_size = cluster_size

    def analyze(self, extent_analysis):
        if not isinstance(
            extent_analysis,
            ExtentAnalysis,
        ):
            raise TypeError(
                "extent_analysis must be an ExtentAnalysis"
            )

        fragments = []

        current_state = None
        current_start_cluster = None
        current_cluster_count = 0
        sequence = 0

        for index, state in enumerate(
            extent_analysis.states
        ):
            cluster = (
                extent_analysis.start_cluster
                + index
            )

            if state != current_state:
                if current_state == "unallocated":
                    fragments.append(
                        self._create_fragment(
                            extent_analysis,
                            current_start_cluster,
                            current_cluster_count,
                            sequence,
                        )
                    )
                    sequence += 1

                current_state = state
                current_start_cluster = cluster
                current_cluster_count = 1

            else:
                current_cluster_count += 1

        if current_state == "unallocated":
            fragments.append(
                self._create_fragment(
                    extent_analysis,
                    current_start_cluster,
                    current_cluster_count,
                    sequence,
                )
            )

        complete = (
            extent_analysis.all_unallocated
            and len(fragments) == 1
        )

        return FragmentAnalysis(
            fragments=fragments,
            complete=complete,
        )

    def _create_fragment(
        self,
        extent_analysis,
        start_cluster,
        cluster_count,
        sequence,
    ):
        return RecoveryFragment(
            source_offset=self.geometry.cluster_offset(start_cluster),
            size=cluster_count * self.cluster_size,
            sequence=sequence,
        )