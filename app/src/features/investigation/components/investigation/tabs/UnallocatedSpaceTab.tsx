import { useCallback, useEffect, useRef, useState } from "react";
import { unallocatedSpaceService } from "../../../services/unallocated.service";
import type { UnallocatedRegion } from "../../../types/unallocated-space";

interface Props {
    imagePath: string;
    databasePath: string;
    caseId: number | null;
    selectedRegionIndex: number | null;
    onSelectRegion: (index: number | null) => void;
}

const READ_SIZE = 256;

function formatBytes(value: number): string {
    if (value < 1024) return `${value} B`;
    if (value < 1024 ** 2) return `${(value / 1024).toFixed(2)} KB`;
    if (value < 1024 ** 3) return `${(value / 1024 ** 2).toFixed(2)} MB`;
    return `${(value / 1024 ** 3).toFixed(2)} GB`;
}

function hexToBytes(hex: string): number[] {
    const bytes: number[] = [];
    for (let i = 0; i < hex.length; i += 2) {
        bytes.push(Number.parseInt(hex.slice(i, i + 2), 16));
    }
    return bytes;
}

export default function UnallocatedSpaceTab({
    imagePath,
    databasePath,
    caseId,
    selectedRegionIndex,
    onSelectRegion,
}: Props) {
    const [regions, setRegions] = useState<UnallocatedRegion[]>([]);
    const selectedIndex = selectedRegionIndex;
    const [offset, setOffset] = useState(0);
    const [hexData, setHexData] = useState("");
    const [loadingRegions, setLoadingRegions] = useState(false);
    const [loadingBytes, setLoadingBytes] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Read the current selection through a ref so that selecting a region
    // does not re-create loadRegions and reload the whole region list.
    const selectedRegionRef = useRef(selectedRegionIndex);
    selectedRegionRef.current = selectedRegionIndex;

    const loadRegions = useCallback(async () => {
        if (!imagePath || !databasePath || caseId === null) {
            setRegions([]);
            onSelectRegion(null);
            setOffset(0);
            setHexData("");
            setError("Select an analyzed evidence image and case first.");
            return;
        }

        setLoadingRegions(true);
        setError(null);

        try {
            const response = await unallocatedSpaceService.loadRegions(
                imagePath,
                databasePath,
                caseId,
            );

            setRegions(response.regions);

            const currentIndex = selectedRegionRef.current;
            const nextIndex = response.regions.some(
                (region) => region.index === currentIndex
            )
                ? currentIndex
                : response.regions[0]?.index ?? null;
            
            onSelectRegion(nextIndex)
            setOffset(0);
            setHexData("");

        } catch (err) {
            setError(err instanceof Error ? err.message : String(err));
            setRegions([]);
            onSelectRegion(null);
            setOffset(0);
            setHexData("");
        } finally {
            setLoadingRegions(false);
        }
    }, [
        imagePath, 
        databasePath, 
        caseId,
        onSelectRegion,
    ]);

    useEffect(() => {
        void loadRegions();
    }, [loadRegions]);

    const selectedRegion =
        selectedIndex === null
            ? undefined
            : regions.find((region) => region.index === selectedIndex);

    const readBytes = useCallback(async () => {
        if (!selectedRegion || !imagePath || !databasePath || caseId === null) {
            return;
        }

        if (offset < 0 || offset >= selectedRegion.byte_count) {
            setError("The offset is outside the selected region.");
            setHexData("");
            return;
        }

        const size = Math.min(
            READ_SIZE,
            selectedRegion.byte_count - offset,
        );

        setLoadingBytes(true);
        setError(null);

        try {
            const response = await unallocatedSpaceService.readRegion(
                imagePath,
                databasePath,
                caseId,
                selectedRegion.index,
                offset,
                size,
            );
            setHexData(response.data);
        } catch (err) {
            setError(err instanceof Error ? err.message : String(err));
            setHexData("");
        } finally {
            setLoadingBytes(false);
        }
    }, [selectedRegion, imagePath, databasePath, caseId, offset]);

    useEffect(() => {
        void readBytes();
    }, [readBytes]);

    const bytes = hexToBytes(hexData);

    return (
        <div className="flex h-full min-h-0 flex-col bg-white text-slate-800">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b p-3">
                <div>
                    <h3 className="font-semibold">Unallocated Space</h3>
                    <p className="text-xs text-slate-500">
                        Read-only raw-byte inspection
                    </p>
                </div>

                <button
                    type="button"
                    onClick={() => void loadRegions()}
                    disabled={loadingRegions}
                    className="rounded border px-3 py-1.5 text-sm hover:bg-slate-50 disabled:opacity-50"
                >
                    {loadingRegions ? "Loading…" : "Refresh regions"}
                </button>
            </div>

            {error && (
                <div
                    role="alert"
                    className="border-b border-red-200 bg-red-50 p-3 text-sm text-red-700"
                >
                    {error}
                </div>
            )}

            <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[minmax(220px,30%)_minmax(0,1fr)]">
                <aside className="min-h-0 overflow-auto border-b lg:border-b-0 lg:border-r">
                    <div className="sticky top-0 border-b bg-slate-50 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                        Regions ({regions.length})
                    </div>

                    {loadingRegions ? (
                        <p className="p-3 text-sm text-slate-500">
                            Enumerating unallocated regions…
                        </p>
                    ) : regions.length === 0 ? (
                        <p className="p-3 text-sm text-slate-500">
                            No regions available.
                        </p>
                    ) : (
                        regions.map((region) => (
                            <button
                                type="button"
                                key={region.index}
                                onClick={() => {
                                    onSelectRegion(region.index);
                                    setOffset(0);
                                    setHexData("");
                                }}
                                className={`block w-full border-b p-3 text-left ${
                                    selectedIndex === region.index
                                        ? "bg-indigo-50 ring-1 ring-inset ring-indigo-200"
                                        : "hover:bg-slate-50"
                                }`}
                            >
                                <div className="flex items-center justify-between gap-2">
                                    <span className="text-sm font-semibold">
                                        Region {region.index}
                                    </span>
                                    <span className="text-xs text-slate-500">
                                        {region.state}
                                    </span>
                                </div>
                                <div className="mt-1 text-xs text-slate-600">
                                    Clusters: {region.start_cluster.toLocaleString()}–
                                    {region.end_cluster.toLocaleString()}
                                </div>
                                <div className="mt-1 text-xs text-slate-500">
                                    {formatBytes(region.byte_count)}
                                </div>
                                <div className="mt-1 break-all font-mono text-xs text-slate-500">
                                    Offset: 0x{region.start_offset.toString(16)}
                                </div>
                            </button>
                        ))
                    )}
                </aside>

                <section className="flex min-h-0 min-w-0 flex-col">
                    {!selectedRegion ? (
                        <div className="flex flex-1 items-center justify-center p-4 text-sm text-slate-500">
                            Select an unallocated region to inspect its bytes.
                        </div>
                    ) : (
                        <>
                            <div className="flex flex-wrap items-center justify-between gap-3 border-b p-3">
                                <div className="text-sm">
                                    <div className="font-semibold">
                                        Region {selectedRegion.index}
                                    </div>
                                    <div className="text-xs text-slate-500">
                                        {formatBytes(selectedRegion.byte_count)} total
                                    </div>
                                </div>

                                <div className="flex items-center gap-2">
                                    <label
                                        htmlFor="unallocated-offset"
                                        className="text-xs text-slate-600"
                                    >
                                        Relative offset
                                    </label>
                                    <input
                                        id="unallocated-offset"
                                        type="number"
                                        min={0}
                                        max={Math.max(0, selectedRegion.byte_count - 1)}
                                        step={16}
                                        value={offset}
                                        onChange={(event) => {
                                            const next = Number(event.target.value);
                                            if (
                                                Number.isSafeInteger(next) &&
                                                next >= 0 &&
                                                next < selectedRegion.byte_count
                                            ) {
                                                setOffset(next);
                                            }
                                        }}
                                        className="w-28 rounded border px-2 py-1 font-mono text-sm"
                                    />
                                </div>
                            </div>

                            <div className="flex flex-wrap gap-2 border-b p-2">
                                <button
                                    type="button"
                                    disabled={loadingBytes || offset === 0}
                                    onClick={() => setOffset(Math.max(0, offset - READ_SIZE))}
                                    className="rounded border px-3 py-1 text-sm disabled:opacity-40"
                                >
                                    Previous 256 bytes
                                </button>
                                <button
                                    type="button"
                                    disabled={
                                        loadingBytes ||
                                        offset + READ_SIZE >= selectedRegion.byte_count
                                    }
                                    onClick={() =>
                                        setOffset(
                                            Math.min(
                                                selectedRegion.byte_count - 1,
                                                offset + READ_SIZE,
                                            ),
                                        )
                                    }
                                    className="rounded border px-3 py-1 text-sm disabled:opacity-40"
                                >
                                    Next 256 bytes
                                </button>
                                <button
                                    type="button"
                                    disabled={loadingBytes}
                                    onClick={() => void readBytes()}
                                    className="rounded border px-3 py-1 text-sm disabled:opacity-40"
                                >
                                    Read current offset
                                </button>
                            </div>

                            <div className="min-h-0 flex-1 overflow-auto p-3">
                                {loadingBytes ? (
                                    <p className="text-sm text-slate-500">
                                        Reading raw bytes…
                                    </p>
                                ) : hexData ? (
                                    <div className="min-w-max font-mono text-xs">
                                        <div className="mb-2 grid grid-cols-[100px_minmax(360px,1fr)_160px] gap-3 border-b pb-2 font-semibold text-slate-500">
                                            <span>Offset</span>
                                            <span>Hex bytes</span>
                                            <span>ASCII</span>
                                        </div>

                                        {Array.from(
                                            { length: Math.ceil(bytes.length / 16) },
                                            (_, rowIndex) => {
                                                const row = bytes.slice(
                                                    rowIndex * 16,
                                                    rowIndex * 16 + 16,
                                                );
                                                const rowOffset =
                                                    offset + rowIndex * 16;

                                                const hex = row
                                                    .map((byte) =>
                                                        byte.toString(16).padStart(2, "0"),
                                                    )
                                                    .join(" ");

                                                const ascii = row
                                                    .map((byte) =>
                                                        byte >= 32 && byte <= 126
                                                            ? String.fromCharCode(byte)
                                                            : ".",
                                                    )
                                                    .join("");

                                                return (
                                                    <div
                                                        key={rowOffset}
                                                        className="grid grid-cols-[100px_minmax(360px,1fr)_160px] gap-3 border-b border-slate-100 py-1 hover:bg-slate-50"
                                                    >
                                                        <span className="text-slate-500">
                                                            {(selectedRegion.start_offset + rowOffset)
                                                                .toString(16)
                                                                .padStart(12, "0")}
                                                        </span>
                                                        <span className="whitespace-pre text-slate-800">
                                                            {hex}
                                                        </span>
                                                        <span className="whitespace-pre text-slate-600">
                                                            {ascii}
                                                        </span>
                                                    </div>
                                                );
                                            },
                                        )}
                                    </div>
                                ) : (
                                    <p className="text-sm text-slate-500">
                                        No bytes loaded at this offset.
                                    </p>
                                )}
                            </div>

                            <div className="border-t bg-slate-50 px-3 py-2 text-xs text-slate-500">
                                {loadingBytes
                                    ? "Reading…"
                                    : `${bytes.length} bytes displayed · Maximum read size: ${READ_SIZE} bytes`}
                            </div>
                        </>
                    )}
                </section>
            </div>
        </div>
    );
}