import re

# Runs of bytes where all 8 clusters share one state.
_UNIFORM_BYTES = re.compile(rb"\x00{2,}|\xff{2,}")


class BitmapAllocationError(Exception):
    """Raised when NTFS $Bitmap data cannot be interpreted safely."""


def read_data_runs(
    image,
    runs,
    cluster_size,
    real_size,
    volume_offset = 0
):
    """
    Read the bytes represented by an NTFS non-resident
    data-run list.

    Only non-sparse runs are read from the image.

    Parameters:
        image:
            Open binary evidence-image handle.

        runs:
            Output of parse_data_runs().

        cluster_size:
            NTFS bytes per cluster.

        real_size:
            Logical size of the attribute in bytes.

    Returns:
        bytes containing the logical stream data.
    """

    if cluster_size <= 0:
        raise BitmapAllocationError(
            "Cluster size must be greater than zero"
        )

    # bool is a subclass of int in Python; reject it explicitly.
    if (
        not isinstance(volume_offset, int)
        or isinstance(volume_offset, bool)
        or volume_offset < 0
    ):
        raise BitmapAllocationError(
            "Volume offset must be a non-negative integer"
        )

    if real_size < 0:
        raise BitmapAllocationError(
            "Real size cannot be negative"
        )

    if not runs:
        if real_size == 0:
            return b""

        raise BitmapAllocationError(
            "Non-empty stream has no data runs"
        )

    data = bytearray()

    for run in runs:

        if run["length"] < 0:
            raise BitmapAllocationError(
                "Data-run length cannot be negative"
            )

        if run["sparse"]:

            # Sparse clusters logically contain zero bytes.
            data.extend(
                b"\x00"
                *
                (
                    run["length"]
                    *
                    cluster_size
                )
            )

            continue

        lcn = run["lcn"]

        if lcn is None or lcn < 0:
            raise BitmapAllocationError(
                "Non-sparse data run has invalid LCN"
            )

        byte_offset = volume_offset + lcn * cluster_size

        byte_length = (
            run["length"]
            *
            cluster_size
        )

        image.seek(byte_offset)

        chunk = image.read(byte_length)

        if len(chunk) != byte_length:
            raise BitmapAllocationError(
                f"Unable to read complete data run: "
                f"LCN={lcn}, "
                f"expected={byte_length}, "
                f"received={len(chunk)}"
            )

        data.extend(chunk)

    # A non-resident stream may have cluster padding.
    # Return only its logical size.
    if len(data) < real_size:
        raise BitmapAllocationError(
            f"Data runs produced insufficient data: "
            f"expected={real_size}, "
            f"received={len(data)}"
        )

    return bytes(data[:real_size])

def load_bitmap(
    image,
    bitmap_runs,
    cluster_size,
    bitmap_size,
    volume_offset = 0
):
    """
    Read the complete NTFS $Bitmap stream from its data runs.
    """

    if bitmap_size < 0:
        raise BitmapAllocationError(
            "Bitmap size cannot be negative"
        )

    bitmap_data = read_data_runs(
        image=image,
        runs=bitmap_runs,
        cluster_size=cluster_size,
        real_size=bitmap_size,
        volume_offset=volume_offset,
    )

    if len(bitmap_data) != bitmap_size:
        raise BitmapAllocationError(
            f"Bitmap size mismatch: "
            f"expected={bitmap_size}, "
            f"received={len(bitmap_data)}"
        )

    return bitmap_data


def decode_bitmap(bitmap_data, total_clusters):
    """
    Decode an NTFS $Bitmap byte array.

    NTFS bitmap semantics:
        bit = 0 -> cluster is unallocated
        bit = 1 -> cluster is allocated

    Cluster N is represented by:
        byte_index = N // 8
        bit_index  = N % 8

    Returns:
        List of allocation ranges.

    Each range has:
        start_cluster
        cluster_count
        end_cluster
        state
    """

    if not isinstance(bitmap_data, (bytes, bytearray)):
        raise BitmapAllocationError(
            "Bitmap data must be bytes or bytearray"
        )

    if total_clusters < 0:
        raise BitmapAllocationError(
            "Total cluster count cannot be negative"
        )

    required_bytes = (total_clusters + 7) // 8

    if len(bitmap_data) < required_bytes:
        raise BitmapAllocationError(
            f"Bitmap is too small: "
            f"requires {required_bytes} bytes, "
            f"received {len(bitmap_data)} bytes"
        )

    ranges = []

    if total_clusters == 0:
        return ranges

    def add(state, count):
        if ranges and ranges[-1]["state"] == state:
            ranges[-1]["cluster_count"] += count
            ranges[-1]["end_cluster"] += count
        else:
            start = ranges[-1]["end_cluster"] + 1 if ranges else 0
            ranges.append({
                "start_cluster": start,
                "cluster_count": count,
                "end_cluster": start + count - 1,
                "state": state,
            })

    def add_bits(byte_value, clusters):
        for bit in range(clusters):
            add("allocated" if (byte_value >> bit) & 1 else "unallocated", 1)

    # Whole bytes of 0x00 / 0xFF are 8 free / 8 used clusters; handle
    # long runs of them at once and only walk mixed bytes bit by bit.
    position = 0
    for match in _UNIFORM_BYTES.finditer(bitmap_data, 0, required_bytes):
        for byte_value in bitmap_data[position:match.start()]:
            add_bits(byte_value, 8)
        state = "allocated" if bitmap_data[match.start()] == 0xFF else "unallocated"
        add(state, 8 * (match.end() - match.start()))
        position = match.end()
    for byte_value in bitmap_data[position:required_bytes]:
        add_bits(byte_value, 8)

    # The last byte may describe clusters past the end of the volume.
    excess = ranges[-1]["end_cluster"] + 1 - total_clusters
    while excess > 0:
        last = ranges[-1]
        trim = min(excess, last["cluster_count"])
        last["cluster_count"] -= trim
        last["end_cluster"] -= trim
        excess -= trim
        if last["cluster_count"] == 0:
            ranges.pop()

    return ranges


if __name__ == "__main__":

    image_path = r"C:\Users\HP\Desktop\mft_parser\test.001"

    bitmap_runs = [
        {
            "run_number": 1,
            "length": 30,
            "lcn": 262113,
            "sparse": False,
        }
    ]

    bitmap_size = 122880
    cluster_size = 4096

    with open(image_path, "rb") as image:

        bitmap_data = load_bitmap(
            image=image,
            bitmap_runs=bitmap_runs,
            cluster_size=cluster_size,
            bitmap_size=bitmap_size
        )

    print("Bitmap loaded successfully")
    print("Bitmap size:", len(bitmap_data))
    print("First 16 bytes:", bitmap_data[:16].hex())

    total_clusters = len(bitmap_data) * 8

    print("Bitmap represented clusters:", total_clusters)

    print("Bitmap represented bytes:", total_clusters * cluster_size)

    ranges = decode_bitmap(
        bitmap_data=bitmap_data,
        total_clusters=total_clusters
    )

    print("Allocation ranges:", len(ranges))

    allocated_clusters = 0
    unallocated_clusters = 0

    for item in ranges:

        if item["state"] == "allocated":
            allocated_clusters += item["cluster_count"]

        elif item["state"] == "unallocated":
            unallocated_clusters += item["cluster_count"]

    print("Allocated clusters:", allocated_clusters)
    print("Unallocated clusters:", unallocated_clusters)

    print("\nFirst 20 allocation ranges:")

    for item in ranges[:20]:
        print(item)