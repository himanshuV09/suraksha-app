import { useCallback, useEffect, useMemo, useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";

import { errorMessage } from "../../../../../lib/engine";
import { deletedFileService } from "../../../services/deleted-file.service";
import type { DeletedFile, DeletedFileStatus } from "../../../types/deleted-file";
import { formatBytes } from "../../../utils/formatBytes";

interface Props {
    imagePath: string;
    databasePath: string;
    caseId: number | null;
}

const STATUS_STYLE: Record<DeletedFileStatus, string> = {
    recoverable: "bg-emerald-100 text-emerald-700",
    partial: "bg-amber-100 text-amber-800",
    overwritten: "bg-red-100 text-red-700",
    no_data: "bg-slate-200 text-slate-600",
};

const STATUS_HELP: Record<DeletedFileStatus, string> = {
    recoverable: "All data is still on disk",
    partial: "Some clusters now hold other data",
    overwritten: "All clusters now hold other data",
    no_data: "Empty file",
};

const FILTERS: (DeletedFileStatus | "all")[] = ["all", "recoverable", "partial", "overwritten", "no_data"];

export default function DeletedFilesTab({ imagePath, databasePath, caseId }: Props) {
    const [files, setFiles] = useState<DeletedFile[]>([]);
    const [filter, setFilter] = useState<DeletedFileStatus | "all">("all");
    const [selected, setSelected] = useState<Set<number>>(new Set());
    const [loading, setLoading] = useState(false);
    const [recovering, setRecovering] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [message, setMessage] = useState<string | null>(null);

    const load = useCallback(async () => {
        if (!databasePath || caseId === null) {
            setError("Analyze an evidence image first.");
            return;
        }
        setLoading(true);
        setError(null);
        try {
            const response = await deletedFileService.load(databasePath, caseId);
            setFiles(response.files);
            setSelected(new Set());
        } catch (err) {
            setFiles([]);
            setError(errorMessage(err));
        } finally {
            setLoading(false);
        }
    }, [databasePath, caseId]);

    useEffect(() => {
        void load();
    }, [load]);

    const counts = useMemo(() => {
        const result: Record<string, number> = { all: files.length };
        for (const file of files) {
            result[file.status] = (result[file.status] ?? 0) + 1;
        }
        return result;
    }, [files]);

    const visible = filter === "all" ? files : files.filter((file) => file.status === filter);

    const toggle = (record: number) => {
        setSelected((current) => {
            const next = new Set(current);
            if (next.has(record)) {
                next.delete(record);
            } else {
                next.add(record);
            }
            return next;
        });
    };

    const recover = useCallback(async (recordNumbers?: number[]) => {
        if (!imagePath || !databasePath || caseId === null) {
            return;
        }
        const destination = await open({ directory: true, multiple: false });
        if (!destination || Array.isArray(destination)) {
            return;
        }
        setRecovering(true);
        setError(null);
        setMessage(null);
        try {
            const result = await deletedFileService.recover(
                imagePath, databasePath, caseId, destination,
                recordNumbers
                    // Chosen files are restored whatever their grade.
                    ? { recordNumbers, statuses: ["recoverable", "partial", "overwritten", "no_data"] }
                    : { statuses: ["recoverable"] },
            );
            setMessage(
                `Restored ${result.recovered_count} file(s), ${formatBytes(result.recovered_bytes)}, ` +
                `to ${result.destination}. Hashes and unreliable byte ranges are in ${result.manifest}` +
                (result.failed_count ? `. ${result.failed_count} failed.` : "."),
            );
        } catch (err) {
            setError(errorMessage(err));
        } finally {
            setRecovering(false);
        }
    }, [imagePath, databasePath, caseId]);

    return (
        <div className="flex h-full min-h-0 flex-col bg-white text-slate-800">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b p-3">
                <div>
                    <h3 className="font-semibold">Deleted Files</h3>
                    <p className="text-xs text-slate-500">
                        Graded against $Bitmap, other deleted files and the file's own content
                    </p>
                </div>
                <div className="flex flex-wrap gap-2">
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
                        onClick={() => void recover([...selected])}
                        disabled={recovering || selected.size === 0}
                        className="rounded border px-3 py-1.5 text-sm hover:bg-slate-50 disabled:opacity-50"
                    >
                        Recover selected ({selected.size})…
                    </button>
                    <button
                        type="button"
                        onClick={() => void recover()}
                        disabled={recovering || !counts.recoverable}
                        className="rounded border border-indigo-600 px-3 py-1.5 text-sm text-indigo-700 hover:bg-indigo-50 disabled:opacity-50"
                    >
                        {recovering ? "Recovering…" : `Recover all recoverable (${counts.recoverable ?? 0})…`}
                    </button>
                </div>
            </div>

            <div className="flex flex-wrap gap-1 border-b px-3 py-2">
                {FILTERS.map((option) => (
                    <button
                        type="button"
                        key={option}
                        onClick={() => setFilter(option)}
                        className={`rounded px-2 py-1 text-xs ${
                            filter === option ? "bg-indigo-600 text-white" : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                        }`}
                    >
                        {option.replace("_", " ")} ({counts[option] ?? 0})
                    </button>
                ))}
            </div>

            {error && (
                <div role="alert" className="border-b border-red-200 bg-red-50 p-3 text-sm text-red-700">
                    {error}
                </div>
            )}
            {message && (
                <div className="border-b border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">
                    {message}
                </div>
            )}

            <div className="min-h-0 flex-1 overflow-auto">
                {visible.length === 0 && !loading ? (
                    <p className="p-3 text-sm text-slate-500">
                        No deleted files here. Cases analyzed before this feature need re-analysis.
                    </p>
                ) : (
                    <table className="w-full text-left text-sm">
                        <thead className="sticky top-0 bg-slate-100 text-xs uppercase text-slate-500">
                            <tr>
                                <th className="px-3 py-2" />
                                <th className="px-3 py-2">Name</th>
                                <th className="px-3 py-2">Status</th>
                                <th className="px-3 py-2 text-right">Size</th>
                                <th className="px-3 py-2 text-right">Recoverable</th>
                                <th className="px-3 py-2">Content</th>
                                <th className="px-3 py-2">Overwritten by</th>
                                <th className="px-3 py-2">Modified</th>
                            </tr>
                        </thead>
                        <tbody>
                            {visible.map((file) => (
                                <tr key={file.record_number} className="border-b hover:bg-slate-50">
                                    <td className="px-3 py-1.5">
                                        <input
                                            type="checkbox"
                                            aria-label={`Select ${file.filename}`}
                                            checked={selected.has(file.record_number)}
                                            onChange={() => toggle(file.record_number)}
                                        />
                                    </td>
                                    <td className="max-w-xs truncate px-3 py-1.5" title={file.full_path}>
                                        {file.full_path || file.filename}
                                    </td>
                                    <td className="px-3 py-1.5">
                                        <span
                                            title={STATUS_HELP[file.status]}
                                            className={`rounded px-1.5 py-0.5 text-xs ${STATUS_STYLE[file.status]}`}
                                        >
                                            {file.status.replace("_", " ")}
                                        </span>
                                    </td>
                                    <td className="px-3 py-1.5 text-right">{formatBytes(file.file_size)}</td>
                                    <td className="px-3 py-1.5 text-right">{file.recoverable_percent}%</td>
                                    <td className="px-3 py-1.5 text-xs text-slate-600">{file.content_check}</td>
                                    <td className="max-w-xs truncate px-3 py-1.5 text-xs text-slate-600" title={file.overwritten_by.join("\n")}>
                                        {file.overwritten_by.join(", ") || "—"}
                                    </td>
                                    <td className="px-3 py-1.5 font-mono text-xs">{file.modified?.slice(0, 19) ?? "—"}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}
            </div>
        </div>
    );
}
