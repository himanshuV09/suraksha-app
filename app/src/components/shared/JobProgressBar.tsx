import type { JobProgress } from "../../lib/engine";

interface Props {
    progress: JobProgress | null;
    onCancel?: () => void;
    label?: string;
}

function percent(progress: JobProgress | null): number | null {
    if (!progress || !progress.total || progress.done === null) {
        return null;
    }
    return Math.min(100, Math.round((progress.done / progress.total) * 100));
}

/** Progress of a running engine job, with a Cancel button. */
export default function JobProgressBar({ progress, onCancel, label = "Working…" }: Props) {
    const value = percent(progress);

    return (
        <div className="rounded-lg border border-indigo-200 bg-indigo-50 p-3" role="status" aria-live="polite">
            <div className="mb-2 flex items-center justify-between gap-3 text-sm">
                <span className="font-medium text-indigo-900">
                    {progress?.stage || label}
                    {progress?.total ? (
                        <span className="ml-2 font-normal text-indigo-700">
                            {progress.done?.toLocaleString()} / {progress.total.toLocaleString()}
                        </span>
                    ) : null}
                </span>
                {onCancel && (
                    <button
                        type="button"
                        onClick={onCancel}
                        className="rounded border border-indigo-300 bg-white px-2 py-0.5 text-xs text-indigo-700 hover:bg-indigo-100"
                    >
                        Cancel
                    </button>
                )}
            </div>
            <div className="h-2 overflow-hidden rounded bg-indigo-100">
                <div
                    className={`h-full bg-indigo-600 transition-all ${value === null ? "w-1/3 animate-pulse" : ""}`}
                    style={value === null ? undefined : { width: `${value}%` }}
                />
            </div>
        </div>
    );
}
