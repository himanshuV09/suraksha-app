
from pathlib import Path

from database.mapper.filesystem_mapper import FilesystemMapper


def create_node(
    name,
    is_directory=True,
    evidence=None,
    artifact=None,
    node_type=None,
    filesystem=None,
    start_offset=None,
    size=None,
    deleted=False,
):
    """Create a tree node while preserving the existing frontend contract."""
    return {
        "name": name,
        "directory": is_directory,
        "evidence": evidence,
        "artifact": artifact,
        "children": {},
        "nodeType": node_type or (
            "directory" if is_directory else "file"
        ),
        "filesystem": filesystem,
        "startOffset": start_offset,
        "size": size,
        "deleted": deleted,
    }


def _add_child(parent, name, **kwargs):
    """Reuse existing path nodes instead of creating duplicate folders."""
    if name not in parent["children"]:
        parent["children"][name] = create_node(name, **kwargs)

    return parent["children"][name]


def _path_parts(path):
    """Normalize Windows and POSIX separators for tree construction."""
    if not path:
        return []

    return [
        part
        for part in str(path).replace("\\", "/").split("/")
        if part and part != "."
    ]


def build_filesystem_tree(
    evidence_database,
    image_name=None,
    unallocated_regions=None,
):
    """
    Build a tree from parsed evidence and discovered unallocated regions.

    evidence_database:
        Dictionary of record_number -> mapped evidence object.

    image_name:
        Filename of the original evidence image, not the case database.

    unallocated_regions:
        SQLite rows from Repository.get_unallocated_regions().
    """
    image_root = create_node(
        image_name or "Evidence Image",
        is_directory=True,
        node_type="image",
    )

    root_directory = _add_child(
        image_root,
        "[root]",
        is_directory=True,
        node_type="directory",
    )

    unallocated_node = _add_child(
        image_root,
        "[unallocated space]",
        is_directory=True,
        node_type="unallocated",
    )

    # Build the parsed filesystem hierarchy.
    for evidence in evidence_database.values():
        full_path = getattr(evidence, "full_path", None)
        parts = _path_parts(full_path)

        if not parts:
            continue

        current = root_directory

        for index, part in enumerate(parts):
            is_last = index == len(parts) - 1

            is_directory = (
                bool(evidence.directory)
                if is_last
                else True
            )

            current = _add_child(
                current,
                part,
                is_directory=is_directory,
                node_type=(
                    "directory" if is_directory else "file"
                ),
            )

            if is_last:
                current["directory"] = bool(evidence.directory)
                current["nodeType"] = (
                    "directory"
                    if evidence.directory
                    else "file"
                )
                current["evidence"] = (
                    FilesystemMapper.to_dictionary(evidence)
                )
                current["artifact"] = None
                current["size"] = getattr(
                    evidence, "file_size", None
                )
                current["deleted"] = bool(
                    getattr(evidence, "deleted", False)
                )

        # Preserve container artifacts attached by FilesystemAPI.
        for artifact in getattr(evidence, "children", None) or []:
            add_container_path(current, artifact, evidence)

    # Display only regions actually discovered and stored in SQLite.
    for region in unallocated_regions or []:
        (
            region_id,
            _case_id,
            _image_path,
            start_cluster,
            end_cluster,
            cluster_count,
            start_offset,
            end_offset,
            byte_count,
            state,
        ) = region

        region_name = (
            f"Region {region_id} "
            f"(offset 0x{start_offset:X}, {byte_count:,} bytes)"
        )

        region_node = _add_child(
            unallocated_node,
            region_name,
            is_directory=False,
            node_type="unallocated",
            start_offset=start_offset,
            size=byte_count,
        )

        # Additional metadata for future region selection/viewing.
        region_node["regionId"] = region_id
        region_node["startCluster"] = start_cluster
        region_node["endCluster"] = end_cluster
        region_node["clusterCount"] = cluster_count
        region_node["endOffset"] = end_offset
        region_node["state"] = state

    return image_root


def add_container_path(parent_node, artifact, parent_evidence):
    """Add a container member under its parent evidence node."""
    parts = _path_parts(getattr(artifact, "path", None))

    if not parts:
        return

    current = parent_node

    for index, part in enumerate(parts):
        is_last = index == len(parts) - 1

        is_directory = (
            bool(artifact.directory)
            if is_last
            else True
        )

        current = _add_child(
            current,
            part,
            is_directory=is_directory,
            node_type=(
                "directory" if is_directory else "file"
            ),
        )

        if is_last:
            current["directory"] = bool(artifact.directory)
            current["nodeType"] = (
                "directory"
                if artifact.directory
                else "file"
            )
            current["evidence"] = (
                FilesystemMapper.to_dictionary(parent_evidence)
            )
            current["artifact"] = {
                "artifact_id": artifact.artifact_id,
                "case_id": artifact.case_id,
                "parent_record": artifact.parent_record,
                "path": artifact.path,
                "name": artifact.name,
                "directory": artifact.directory,
                "size": artifact.size,
                "mime_type": artifact.mime_type,
            }
            current["size"] = artifact.size


def print_tree(node, indent=""):
    """Print a tree for backend debugging."""
    print(indent + node["name"])

    for child in node["children"].values():
        print_tree(child, indent + "    ")
