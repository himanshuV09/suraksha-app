import { useCallback, useEffect, useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";

import { errorMessage } from "../../../../../lib/engine";
import { metafileService } from "../../../services/metafile.service";
import type { Metafile } from "../../../types/metafile";
import { formatBytes } from "../../../utils/formatBytes";

interface Props {
    imagePath: string;
    databasePath: string;
    caseId: number | null;
}

const STATUS_STYLE: Record<Metafile["status"] | "suspicious", string> = {
    ok: "bg-emerald-100 text-emerald-700",
    missing: "bg-slate-200 text-slate-600",
    error: "bg-red-100 text-red-700",
    suspicious: "bg-red-600 text-white",
};

/** Long lists (object IDs, owners, ...) are cut to keep the panel usable. */
const MAX_LIST_ITEMS = 50;

/** Reserved MFT records that hold data are flagged by the engine. */
function badge(item: Metafile): keyof typeof STATUS_STYLE {
    return item.details.suspicious === true ? "suspicious" : item.status;
}

/** Human-readable label for a details key, e.g. "matches_mft" -> "Matches mft". */
function label(key: string): string {
    const text = key.replace(/_/g, " ");
    return text.charAt(0).toUpperCase() + text.slice(1);
}

function DetailValue({ value }: { value: unknown }) {
    if (value === null || value === undefined) {
        return <span className="text-slate-400">—</span>;
    }
    if (typeof value === "boolean") {
        return (
            <span className={value ? "text-emerald-700" : "text-red-700"}>
                {value ? "Yes" : "No"}
            </span>
        );
    }
    if (Array.isArray(value)) {
        if (value.length === 0) {
            return <span className="text-slate-400">none</span>;
        }
        const shown = value.slice(0, MAX_LIST_ITEMS);
        return (
            <ul className="space-y-0.5">
                {shown.map((item, index) => (
                    <li key={index} className="font-mono text-xs">
                        {typeof item === "object" && item !== null
                            ? Object.values(item).filter((part) => part !== null).join(" · ")
                            : String(item)}
                    </li>
                ))}
                {value.length > shown.length && (
                    <li className="text-xs text-slate-400">
                        +{value.length - shown.length} more
                    </li>
                )}
            </ul>
        );
    }
    if (typeof value === "object") {
        return (
            <ul className="space-y-0.5">
                {Object.entries(value as Record<string, unknown>).map(([key, item]) => (
                    <li key={key} className="font-mono text-xs">
                        {key}: {String(item)}
                    </li>
                ))}
            </ul>
        );
    }
    return <span className="font-mono text-xs">{String(value)}</span>;
}

export default function MetafilesTab({ imagePath, databasePath, caseId }: Props) {
    const [metafiles, setMetafiles] = useState<Metafile[]>([]);
    const [selectedName, setSelectedName] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [exporting, setExporting] = useState(false);
    const [exportMessage, setExportMessage] = useState<string | null>(null);

    const load = useCallback(async () => {
        if (!databasePath || caseId === null) {
            setError("Analyze an evidence image first.");
            return;
        }
        setLoading(true);
        setError(null);
        try {
            const response = await metafileService.load(databasePath, caseId);
            setMetafiles(response.metafiles);
            setSelectedName((current) =>
                response.metafiles.some((item) => item.name === current)
                    ? current
                    : response.metafiles[0]?.name ?? null,
            );
        } catch (err) {
            setMetafiles([]);
            setError(errorMessage(err));
        } finally {
            setLoading(false);
        }
    }, [databasePath, caseId]);

    useEffect(() => {
        void load();
    }, [load]);

    const extractAll = useCallback(async () => {
        if (!imagePath || !databasePath || caseId === null) {
            return;
        }
        const destination = await open({ directory: true, multiple: false });
        if (!destination || Array.isArray(destination)) {
            return;
        }
        setExporting(true);
        setExportMessage(null);
        setError(null);
        try {
            const result = await metafileService.extract(
                imagePath, databasePath, caseId, destination,
            );
            setExportMessage(
                `Exported ${result.exported_count} stream(s) to ${result.destination}` +
                (result.skipped_count ? `; ${result.skipped_count} empty sparse stream(s) skipped` : "") +
                (result.failed_count ? `; ${result.failed_count} failed` : ""),
            );
        } catch (err) {
            setError(errorMessage(err));
        } finally {
            setExporting(false);
        }
    }, [imagePath, databasePath, caseId]);

    const selected = metafiles.find((item) => item.name === selectedName);

    return (
        <div className="flex h-full min-h-0 flex-col bg-white text-slate-800">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b p-3">
                <div>
                    <h3 className="font-semibold">NTFS Metafiles</h3>
                    <p className="text-xs text-slate-500">
                        System files parsed during analysis
                    </p>
                </div>
                <div className="flex gap-2">
                    <button
                        type="button"
                        onClick={() => void load()}
                        disabled={loading}
                        className="rounded border px-3 py-1.5 text-sm hover:bg-slate-50 disabled:opacity-50"
                    >
                        {loading ? "Loading…" : "Refresh"}
                    </button>
                    <button
                        type="button"
                        onClick={() => void extractAll()}
                        disabled={exporting || !imagePath}
                        className="rounded border border-indigo-600 px-3 py-1.5 text-sm text-indigo-700 hover:bg-indigo-50 disabled:opacity-50"
                    >
                        {exporting ? "Exporting…" : "Extract all…"}
                    </button>
                </div>
            </div>

            {error && (
                <div role="alert" className="border-b border-red-200 bg-red-50 p-3 text-sm text-red-700">
                    {error}
                </div>
            )}
            {exportMessage && (
                <div className="border-b border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">
                    {exportMessage}
                </div>
            )}

            <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[minmax(220px,30%)_minmax(0,1fr)]">
                <aside className="min-h-0 overflow-auto border-b lg:border-b-0 lg:border-r">
                    {metafiles.length === 0 && !loading ? (
                        <p className="p-3 text-sm text-slate-500">
                            No metafiles stored for this case. Re-analyze the image to parse them.
                        </p>
                    ) : (
                        metafiles.map((item) => (
                            <button
                                type="button"
                                key={item.name}
                                onClick={() => setSelectedName(item.name)}
                                className={`flex w-full items-center justify-between gap-2 border-b px-3 py-2 text-left text-sm ${
                                    selectedName === item.name ? "bg-indigo-50" : "hover:bg-slate-50"
                                }`}
                            >
                                <span className="truncate font-mono">{item.name}</span>
                                <span className={`rounded px-1.5 py-0.5 text-xs ${STATUS_STYLE[badge(item)]}`}>
                                    {badge(item)}
                                </span>
                            </button>
                        ))
                    )}
                </aside>

                <section className="min-h-0 overflow-auto p-4">
                    {selected ? (
                        <dl className="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-2 text-sm">
                            <dt className="text-slate-500">MFT record</dt>
                            <dd className="font-mono text-xs">{selected.record_number}</dd>
                            <dt className="text-slate-500">Size</dt>
                            <dd>{formatBytes(selected.size)}</dd>
                            <dt className="text-slate-500">Fragments</dt>
                            <dd>{selected.fragments}</dd>
                            <dt className="text-slate-500">Streams</dt>
                            <dd className="font-mono text-xs">
                                {selected.streams.map((s) => `${s.name || "(unnamed)"} ${formatBytes(s.size)}`).join(", ") || "—"}
                            </dd>
                            <dt className="text-slate-500">Created</dt>
                            <dd className="font-mono text-xs">{selected.created ?? "—"}</dd>
                            {selected.error && (
                                <>
                                    <dt className="text-red-600">Error</dt>
                                    <dd className="text-red-700">{selected.error}</dd>
                                </>
                            )}
                            {Object.entries(selected.details).map(([key, value]) => (
                                <div key={key} className="contents">
                                    <dt className="text-slate-500">{label(key)}</dt>
                                    <dd><DetailValue value={value} /></dd>
                                </div>
                            ))}
                        </dl>
                    ) : (
                        <p className="text-sm text-slate-500">Select a metafile.</p>
                    )}
                </section>
            </div>
        </div>
    );
}
