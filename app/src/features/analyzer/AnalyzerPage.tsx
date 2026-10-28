import { useState } from "react";
import { FolderOpen, HardDrive, Play } from "lucide-react";
import { open } from "@tauri-apps/plugin-dialog";

import JobProgressBar from "../../components/shared/JobProgressBar";
import { useJob } from "../../hooks/useJob";
import { formatBytes } from "../investigation/utils/formatBytes";
import type { AnalysisResult } from "./types/analysis-result";

interface AnalyzerPageProps {
    onAnalysisCompleted: (result: AnalysisResult) => void;
    onOpenInvestigation: () => void;
}

/** Raw (dd-style) images: the formats the engine reads directly. */
const IMAGE_EXTENSIONS = ["001", "dd", "img", "raw", "bin"];
const INVESTIGATOR_KEY = "suraksha.investigator";

function rememberedInvestigator(): string {
    try {
        return localStorage.getItem(INVESTIGATOR_KEY) ?? "";
    } catch {
        return "";
    }
}

function fileName(path: string) {
    return path.split(/[\\/]/).pop() ?? path;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
    return (
        <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium text-slate-700">{label}</span>
            {children}
        </label>
    );
}

const inputClass =
    "rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500";

export default function AnalyzerPage({ onAnalysisCompleted, onOpenInvestigation }: AnalyzerPageProps) {
    const [imagePath, setImagePath] = useState("");
    const [caseName, setCaseName] = useState("");
    const [investigator, setInvestigator] = useState(rememberedInvestigator);
    const [description, setDescription] = useState("");
    const [result, setResult] = useState<AnalysisResult | null>(null);
    const job = useJob<AnalysisResult>("analyze");

    const browse = async () => {
        const selected = await open({
            multiple: false,
            directory: false,
            title: "Select an evidence image",
            filters: [
                { name: "Raw disk images", extensions: IMAGE_EXTENSIONS },
                { name: "All files", extensions: ["*"] },
            ],
        });
        if (!selected || Array.isArray(selected)) {
            return;
        }
        setImagePath(selected);
        setResult(null);
        job.reset();
        if (!caseName.trim()) {
            setCaseName(fileName(selected).replace(/\.[^.]+$/, ""));
        }
    };

    const analyze = async () => {
        try {
            localStorage.setItem(INVESTIGATOR_KEY, investigator);
        } catch {
            // Remembering the name is only a convenience.
        }
        setResult(null);
        const analysis = await job.run("start_analysis", {
            imagePath,
            caseName: caseName.trim() || undefined,
            investigator: investigator.trim() || undefined,
            description: description.trim() || undefined,
        });
        if (analysis) {
            setResult(analysis);
            onAnalysisCompleted(analysis);
        }
    };

    const canAnalyze = Boolean(imagePath) && Boolean(caseName.trim()) && !job.running;

    return (
        <div className="mx-auto flex max-w-4xl flex-col gap-6 p-8">
            <header>
                <h1 className="text-3xl font-bold text-slate-900">New analysis</h1>
                <p className="mt-1 text-sm text-slate-500">
                    Analyze a raw NTFS disk image (.001, .dd, .img, .raw). The image is only read, never changed.
                </p>
            </header>

            <section className="flex flex-col gap-4 rounded-lg border bg-white p-6 shadow-sm">
                <Field label="Evidence image">
                    <div className="flex gap-2">
                        <input
                            readOnly
                            value={imagePath}
                            placeholder="No image selected"
                            className={`${inputClass} flex-1 font-mono text-xs`}
                        />
                        <button
                            type="button"
                            onClick={() => void browse()}
                            disabled={job.running}
                            className="flex items-center gap-2 rounded-md border px-3 py-2 text-sm hover:bg-slate-50 disabled:opacity-50"
                        >
                            <FolderOpen size={16} />
                            Browse…
                        </button>
                    </div>
                </Field>

                <div className="grid grid-cols-2 gap-4">
                    <Field label="Case name">
                        <input
                            value={caseName}
                            onChange={(event) => setCaseName(event.target.value)}
                            disabled={job.running}
                            maxLength={120}
                            className={inputClass}
                        />
                    </Field>
                    <Field label="Investigator">
                        <input
                            value={investigator}
                            onChange={(event) => setInvestigator(event.target.value)}
                            disabled={job.running}
                            maxLength={120}
                            className={inputClass}
                        />
                    </Field>
                </div>

                <Field label="Description (optional)">
                    <textarea
                        value={description}
                        onChange={(event) => setDescription(event.target.value)}
                        disabled={job.running}
                        rows={2}
                        maxLength={500}
                        className={inputClass}
                    />
                </Field>

                <div className="flex justify-end">
                    <button
                        type="button"
                        onClick={() => void analyze()}
                        disabled={!canAnalyze}
                        className="flex items-center gap-2 rounded-md bg-indigo-600 px-5 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
                    >
                        <Play size={16} />
                        Analyze
                    </button>
                </div>
            </section>

            {job.running && (
                <JobProgressBar progress={job.progress} onCancel={() => void job.cancel()} label="Starting analysis…" />
            )}

            {job.status === "cancelled" && (
                <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
                    Analysis cancelled. The case is listed as interrupted on the Cases page.
                </div>
            )}

            {job.error && (
                <div role="alert" className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                    {job.error}
                </div>
            )}

            {result && <AnalysisSummary result={result} onOpen={onOpenInvestigation} />}
        </div>
    );
}

function AnalysisSummary({ result, onOpen }: { result: AnalysisResult; onOpen: () => void }) {
    const deleted = result.deleted_recovery ?? {};
    const metafiles = result.metafile_counts ?? {};
    const facts: [string, string | number][] = [
        ["Filesystem", `${result.filesystem}${result.volume_label ? ` · "${result.volume_label}"` : ""}`],
        ["Image size", formatBytes(result.image_size)],
        ["Cluster size", formatBytes(result.cluster_size)],
        ["MFT records", result.total_records.toLocaleString()],
        ["Files", result.total_files.toLocaleString()],
        ["Folders", result.total_directories.toLocaleString()],
        ["Deleted files", result.deleted_files.toLocaleString()],
        ["Recoverable deleted files", (deleted.deleted_recoverable ?? 0).toLocaleString()],
        ["Timeline events", result.timeline_events.toLocaleString()],
        ["USN journal records", (metafiles.usn_records ?? 0).toLocaleString()],
        ["Duration", `${result.duration.toFixed(1)} s`],
    ];

    return (
        <section className="rounded-lg border bg-white p-6 shadow-sm">
            <div className="mb-4 flex items-center justify-between">
                <h2 className="flex items-center gap-2 text-lg font-semibold">
                    <HardDrive size={18} className="text-indigo-600" />
                    Analysis complete
                </h2>
                <button
                    type="button"
                    onClick={onOpen}
                    className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
                >
                    Open in Evidence Explorer
                </button>
            </div>
            <dl className="grid grid-cols-3 gap-x-6 gap-y-3 text-sm">
                {facts.map(([label, value]) => (
                    <div key={label}>
                        <dt className="text-xs text-slate-500">{label}</dt>
                        <dd className="font-medium text-slate-900">{value}</dd>
                    </div>
                ))}
            </dl>
            {(result.corrupt_records > 0 || result.warnings.length > 0) && (
                <div className="mt-4 rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
                    {result.corrupt_records > 0 && (
                        <p>{result.corrupt_records} malformed MFT record(s) were skipped.</p>
                    )}
                    {result.warnings.map((warning) => (
                        <p key={warning}>{warning}</p>
                    ))}
                </div>
            )}
        </section>
    );
}
