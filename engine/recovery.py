def read_clusters(image_file, lcn, length, cluster_size, volume_offset=0):
    """Read ``length`` clusters starting at LCN ``lcn``.

    ``volume_offset`` is where the NTFS volume starts inside the image.
    """

    offset = volume_offset + lcn * cluster_size
    size = length * cluster_size

    image_file.seek(offset)

    data = image_file.read(size)

    return data


def recover_non_resident_data(
        image_reader,
        evidence
):
    """Rebuild a non-resident file's bytes from its data runs."""

    file_size = evidence.file_size
    recovered_data = bytearray()

    for run in evidence.data_runs:

        # Clusters past the logical end are slack; no need to read them.
        if len(recovered_data) >= file_size:
            break

        # A sparse run has no clusters on disk; it reads as zeros.
        # It must still take up space, or every later byte shifts.
        if run.get("sparse", False):
            run_bytes = run["length"] * image_reader.cluster_size
            recovered_data.extend(
                bytes(min(run_bytes, file_size - len(recovered_data)))
            )
            continue

        cluster_data = image_reader.read_clusters(
            run["lcn"],
            run["length"],
        )

        recovered_data.extend(cluster_data)

    return bytes(recovered_data[:file_size])


def recover_resident_data(evidence):

    return evidence.resident_data
