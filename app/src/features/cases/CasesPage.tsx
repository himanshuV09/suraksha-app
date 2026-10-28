import { useCallback, useEffect, useState } from "react";
import { FolderOpen, Plus, RefreshCw } from "lucide-react";
import { revealItemInDir } from "@tauri-apps/plugin-opener";

import { callEngine, errorMessage } from "../../lib/engine";
import type { CaseSummary, CasesResponse, EngineInfo } from "./types";

interface Props {
    onOpenCase: (summary: CaseSummary) => void;
    onNewAnalysis: () => void;
}

const STATUS_STYLE: Record<CaseSummary["status"], string> = {
    complete: "bg-emerald-100 text-emerald-800",
    failed: "bg-red-100 text-red-700",
    running: "bg-amber-100 text-amber-800",
    unknown: "bg-slate-200 text-slate-600",
};

const STATUS_LABEL: Record<CaseSummary["status"], string> = {
    complete: "Complete",
    failed: "Failed",
    running: "Interrupted",
    unknown: "Unknown",
};

function when(value: string | null) {
    return value ? value.slice(0, 16).replace("T", " ") : "—";
}

export default function CasesPage({ onOpenCase, onNewAnalysis }: Props) {
    const [cases, setCases] = useState<CaseSummary[]>([]);
    const [info, setInfo] = useState<EngineInfo | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const load = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const response = await callEngine<CasesResponse>("list_cases");
            setCases(response.cases);
        } catch (err) {
            setError(errorMessage(err));
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        void load();
        callEngine<EngineInfo>("engine_info").then(setInfo).catch(() => setInfo(null));
    }, [load]);

    return (
        <div className="flex h-full flex-col gap-6 p-8">
            <header className="flex flex-wrap items-end justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-bold text-slate-900">Cases</h1>
                    <p className="mt-1 text-sm text-slate-500">
                        Open an analyzed case, or analyze a new evidence image.
                    </p>
                </div>
                <div className="flex gap-2">
                    <button
                        type="button"
                        onClick={() => void load()}
                        disabled={loading}
                        className="flex items-center gap-2 rounded-md border bg-white px-3 py-2 text-sm hover:bg-slate-50 disabled:opacity-50"
                    >
                        <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
                        Refresh
                    </button>
                    <button
                        type="button"
                        onClick={onNewAnalysis}
                        className="flex items-center gap-2 rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
                    >
                        <Plus size={16} />
                        New analysis
                    </button>
                </div>
            </header>

            {error && (
                <div role="alert" className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                    {error}
                </div>
            )}

            <section className="min-h-0 flex-1 overflow-auto rounded-lg border bg-white shadow-sm">
                {cases.length === 0 && !loading ? (
                    <div className="flex h-full flex-col items-center justify-center gap-3 p-12 text-center">
                        <p className="text-slate-600">No cases yet.</p>
                        <button
                            type="button"
                            onClick={onNewAnalysis}
                            className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
                        >
                            Analyze an evidence image
                        </button>
                    </div>
                ) : (
                    <table className="w-full text-left text-sm">
                        <thead className="sticky top-0 bg-slate-100 text-xs uppercase text-slate-500">
                            <tr>
                                <th className="px-4 py-3">Case</th>
                                <th className="px-4 py-3">Status</th>
                                <th className="px-4 py-3">Evidence image</th>
                                <th className="px-4 py-3">Investigator</th>
                                <th className="px-4 py-3 text-right">Files</th>
                                <th className="px-4 py-3">Created</th>
                                <th className="px-4 py-3" />
                            </tr>
                        </thead>
                        <tbody>
                            {cases.map((item) => (
                                <tr key={`${item.database_path}#${item.case_id}`} className="border-b hover:bg-slate-50">
                                    <td className="px-4 py-3">
                                        <div className="font-medium text-slate-900">{item.case_name}</div>
                                        {item.description && (
                                            <div className="text-xs text-slate-500">{item.description}</div>
                                        )}
                                        <div className="text-xs text-slate-400">Case #{item.case_id}</div>
                                    </td>
                                    <td className="px-4 py-3">
                                        <span className={`rounded px-2 py-0.5 text-xs font-medium ${STATUS_STYLE[item.status]}`}>
                                            {STATUS_LABEL[item.status]}
                                        </span>
                                    </td>
                                    <td className="max-w-xs px-4 py-3">
                                        <div className="truncate font-mono text-xs" title={item.image_path ?? ""}>
                                            {item.image_path ?? "—"}
                                        </div>
                                        {!item.image_available && item.image_path && (
                                            <div className="text-xs text-amber-700">
                                                Image not found at this path
                                            </div>
                                        )}
                                    </td>
                                    <td className="px-4 py-3">{item.investigator || "—"}</td>
                                    <td className="px-4 py-3 text-right">{item.evidence_count.toLocaleString()}</td>
                                    <td className="px-4 py-3 font-mono text-xs">{when(item.created_at)}</td>
                                    <td className="px-4 py-3 text-right">
                                        <button
                                            type="button"
                                            onClick={() => onOpenCase(item)}
                                            disabled={item.evidence_count === 0}
                                            title={item.evidence_count === 0 ? "This case has no analysis results" : undefined}
                                            className="flex items-center gap-1 rounded-md border px-3 py-1.5 text-xs font-medium hover:bg-indigo-50 disabled:opacity-40"
                                        >
                                            <FolderOpen size={14} />
                                            Open
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}
            </section>

            {info && (
                <footer className="flex flex-wrap items-center gap-x-6 gap-y-1 text-xs text-slate-500">
                    <span>Suraksha {info.app_version} · engine {info.engine_version}</span>
                    <button
                        type="button"
                        className="underline-offset-2 hover:underline"
                        onClick={() => void revealItemInDir(info.cases_dir)}
                        title={info.cases_dir}
                    >
                        Show case folder
                    </button>
                    {info.log_file && (
                        <button
                            type="button"
                            className="underline-offset-2 hover:underline"
                            onClick={() => void revealItemInDir(info.log_file!)}
                            title={info.log_file}
                        >
                            Show log file
                        </button>
                    )}
                </footer>
            )}
        </div>
    );
}
