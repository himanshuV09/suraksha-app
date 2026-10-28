
import TreeNode from "./TreeNode";
import type { FilesystemNode } from "../../types/filesystem";
import type { RecoveredArtifact } from "../../types/recovered-artifact";
import type { UnallocatedRegion } from "../../types/unallocated-space";
import { unallocatedSpaceService } from "../../services/unallocated.service";
import { useEffect, useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import { errorMessage, type JobProgress } from "../../../../lib/engine";
import JobProgressBar from "../../../../components/shared/JobProgressBar";
import { useInvestigation } from "../../context/InvestigationContext";
import { investigationService } from "../../services/investigation.service";
import {
    ChevronDown,
    ChevronRight,
    FileSearch,
    Folder,
    LoaderCircle,
    ScanSearch,
    HardDrive,
    Database,
} from "lucide-react";

interface FileTreeProps {
    tree: FilesystemNode | null;
    loading: boolean;
    recoveredArtifacts: RecoveredArtifact[];
    recoveredArtifactsLoading: boolean;
    recoveredArtifactsError: string | null;
    imagePath: string;
    databasePath: string;
    caseId: number | null;
    onRecoverUnallocated: (
        imagePath: string,
        databasePath: string,
        caseId: number
    ) => Promise<boolean>;
    recoveringUnallocated: boolean;
    recoveryProgress: JobProgress | null;
    onCancelRecovery: () => void;
    recoveryError: string | null;
    recoveryMessage: string | null;
    selectedRegionIndex: number | null;
    onSelectRegion: (index: number | null) => void;
    onOpenUnallocated: () => void;
    onOpenPreview: () => void;
}

export default function FileTree({
    tree,
    loading,
    recoveredArtifacts,
    recoveredArtifactsLoading,
    recoveredArtifactsError,
    imagePath,
    databasePath,
    caseId,
    onRecoverUnallocated,
    recoveringUnallocated,
    recoveryProgress,
    onCancelRecovery,
    recoveryError,
    recoveryMessage,
    selectedRegionIndex,
    onSelectRegion,
    onOpenUnallocated,
    onOpenPreview,
}: FileTreeProps) {
    const { selectedRecovered, setSelectedRecovered } = useInvestigation();
    const [exporting, setExporting] = useState(false);
    const [exportMessage, setExportMessage] = useState<string | null>(null);

    const exportRecovered = async () => {
        if (!imagePath || !databasePath || caseId === null) {
            return;
        }
        const destination = await open({ directory: true, multiple: false });
        if (!destination || Array.isArray(destination)) {
            return;
        }
        setExporting(true);
        setExportMessage(null);
        try {
            const result = await investigationService.exportRecovered(
                imagePath, databasePath, caseId, destination,
            );
            setExportMessage(
                `Exported ${result.exported_count} file(s) to ${result.destination}` +
                (result.hash_mismatches ? `; ${result.hash_mismatches} hash mismatch(es)!` : "; all hashes match."),
            );
        } catch (err) {
            setExportMessage(errorMessage(err));
        } finally {
            setExporting(false);
        }
    };

    const [recoveredExpanded, setRecoveredExpanded] = useState(false);
    const [rawRegionsExpanded, setRawRegionsExpanded] = useState(false);
    const [rawRegions, setRawRegions] = useState<UnallocatedRegion[]>([]);
    const [rawRegionsLoading, setRawRegionsLoading] = useState(false);
    const [rawRegionsError, setRawRegionsError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;

        const loadRawRegions = async () => {
            if (!imagePath || !databasePath || caseId === null) {
                setRawRegions([]);
                setRawRegionsError(null);
                setRawRegionsLoading(false);
                return;
            }

            setRawRegionsLoading(true);
            setRawRegionsError(null);

            try {
                const response = await unallocatedSpaceService.loadRegions(
                    imagePath,
                    databasePath,
                    caseId
                );

                if (!cancelled) {
                    setRawRegions(response.regions);
                }
            } catch (error) {
                if (!cancelled) {
                    setRawRegions([]);
                    setRawRegionsError(
                        error instanceof Error
                            ? error.message
                            : "Failed to load raw regions."
                    );
                }
            } finally {
                if (!cancelled) {
                    setRawRegionsLoading(false);
                }
            }
        };

        void loadRawRegions();

        return () => {
            cancelled = true;
        };
    }, [imagePath, databasePath, caseId]);

    return (
        <aside className="flex h-full flex-col rounded-lg border bg-white shadow-sm">
            <div className="border-b px-4 py-3">
                <h2 className="font-semibold text-slate-800">File Explorer</h2>
            </div>

            <div className="flex-1 overflow-auto p-3">
                {/* File system */}
                <div className="mb-2">
                    <div className="flex items-center gap-2 px-2 py-1 font-medium text-slate-700">
                        <Folder size={16} />
                        <span>File System</span>
                    </div>

                    <div className="ml-2 border-l border-slate-200 pl-2">
                        {loading && (
                            <p className="px-2 py-1 text-sm text-slate-500">
                                Loading filesystem...
                            </p>
                        )}

                        {!loading && !tree && (
                            <p className="px-2 py-1 text-sm text-slate-500">
                                No filesystem loaded.
                            </p>
                        )}

                        {tree && <TreeNode node={tree} />}
                    </div>
                </div>

                {/* Unallocated Space */}
                <div className="mt-3 border-t border-slate-200 pt-3">
                    <button
                        type="button"
                        onClick={() =>
                            setRecoveredExpanded((expanded) => !expanded)
                        }
                        className="flex w-full items-center gap-2 rounded px-2 py-2 text-left hover:bg-slate-100"
                    >
                        {recoveredExpanded ? (
                            <ChevronDown size={14} />
                        ) : (
                            <ChevronRight size={14} />
                        )}

                        <FileSearch size={16} />

                        <span className="font-medium text-slate-700">
                            Unallocated Space
                        </span>

                        <span className="ml-auto text-xs text-slate-500">
                            {recoveredArtifacts.length}
                        </span>
                    </button>

                    {recoveredExpanded && (
                        <div className="ml-4 border-l border-slate-200 pl-3">
                            {/* Raw Regions */}
                            <div className="mb-2">
                                <button
                                    type="button"
                                    onClick={() =>
                                        setRawRegionsExpanded((expanded) => !expanded)
                                    }
                                    className="flex w-full items-center gap-2 rounded px-2 py-2 text-left hover:bg-slate-100"
                                >
                                    {rawRegionsExpanded ? (
                                        <ChevronDown size={14} />
                                    ) : (
                                        <ChevronRight size={14} />
                                    )}

                                    <HardDrive
                                        size={15}
                                        className="text-indigo-600"
                                    />

                                    <span className="text-sm font-medium text-slate-700">
                                        Raw Regions
                                    </span>

                                    <span className="ml-auto text-xs text-slate-500">
                                        {rawRegions.length}
                                    </span>
                                </button>

                                {rawRegionsExpanded && (
                                    <div className="ml-4 border-l border-slate-200 pl-3">
                                        {rawRegionsLoading && (
                                            <p className="px-2 py-2 text-xs text-slate-500">
                                                Loading raw regions...
                                            </p>
                                        )}

                                        {!rawRegionsLoading && rawRegionsError && (
                                            <p
                                                role="alert"
                                                className="break-words px-2 py-2 text-xs text-red-600"
                                            >
                                                {rawRegionsError}
                                            </p>
                                        )}

                                        {!rawRegionsLoading &&
                                            !rawRegionsError &&
                                            rawRegions.length === 0 && (
                                                <p className="px-2 py-2 text-xs text-slate-500">
                                                    No unallocated regions found.
                                                </p>
                                            )}

                                        {!rawRegionsLoading &&
                                            !rawRegionsError &&
                                            rawRegions.map((region) => (
                                                <button
                                                    key={region.index}
                                                    type="button"
                                                    onClick={() => {
                                                        onSelectRegion(region.index);
                                                        onOpenUnallocated();
                                                    }}
                                                    className={`my-1 flex w-full items-start gap-2 rounded px-2 py-2 text-left ${
                                                        selectedRegionIndex === region.index
                                                            ? "bg-indigo-50 text-indigo-700 ring-1 ring-inset ring-indigo-200"
                                                            : "text-slate-700 hover:bg-slate-50"
                                                    }`}
                                                    title={`Offset: ${region.start_offset.toLocaleString()} bytes`}
                                                >
                                                    <Database
                                                        size={14}
                                                        className="mt-0.5 shrink-0"
                                                    />

                                                    <span className="min-w-0">
                                                        <span className="block text-sm font-medium">
                                                            Region {region.index}
                                                        </span>

                                                        <span className="block break-all text-xs text-slate-500">
                                                            {region.byte_count.toLocaleString()} bytes
                                                        </span>

                                                        <span className="block break-all text-xs text-slate-500">
                                                            Clusters{" "}
                                                            {region.start_cluster.toLocaleString()}–
                                                            {region.end_cluster.toLocaleString()}
                                                        </span>
                                                    </span>
                                                </button>
                                            ))}
                                    </div>
                                )}
                            </div>

                            {/* Existing recovery action */}
                            <button
                                type="button"
                                disabled={
                                    !imagePath ||
                                    !databasePath ||
                                    caseId === null ||
                                    recoveringUnallocated
                                }
                                onClick={() => {
                                    if (caseId !== null) {
                                        void onRecoverUnallocated(
                                            imagePath,
                                            databasePath,
                                            caseId
                                        );
                                    }
                                }}
                                className="my-2 flex w-full items-center justify-center gap-2 rounded-md bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
                                title="Scan the selected disk image's unallocated space for recoverable artifacts"
                            >
                                {recoveringUnallocated ? (
                                    <LoaderCircle
                                        size={15}
                                        className="animate-spin"
                                    />
                                ) : (
                                    <ScanSearch size={15} />
                                )}

                                <span>
                                    {recoveringUnallocated
                                        ? "Scanning unallocated space…"
                                        : "Recover Unallocated Space"}
                                </span>
                            </button>

                            {recoveringUnallocated && (
                                <div className="mb-2">
                                    <JobProgressBar
                                        progress={recoveryProgress}
                                        onCancel={onCancelRecovery}
                                        label="Scanning free space…"
                                    />
                                </div>
                            )}

                            {recoveryError && (
                                <p
                                    role="alert"
                                    className="mb-2 break-words px-2 text-xs text-red-600"
                                >
                                    {recoveryError}
                                </p>
                            )}

                            {recoveryMessage && !recoveryError && (
                                <p
                                    role="status"
                                    className="mb-2 break-words px-2 text-xs text-emerald-700"
                                >
                                    {recoveryMessage}
                                </p>
                            )}

                            {/* Existing recovered artifacts list */}
                            <div className="flex items-center gap-2 px-2 py-1 text-sm text-slate-700">
                                <Folder size={15} />
                                <span>Recovered Artifacts</span>
                                {recoveredArtifacts.length > 0 && (
                                    <button
                                        type="button"
                                        onClick={() => void exportRecovered()}
                                        disabled={exporting}
                                        className="ml-auto rounded border px-2 py-0.5 text-xs hover:bg-slate-100 disabled:opacity-50"
                                    >
                                        {exporting ? "Exporting…" : "Export all…"}
                                    </button>
                                )}
                            </div>

                            {exportMessage && (
                                <p className="px-2 py-1 text-xs text-slate-600">{exportMessage}</p>
                            )}

                            {recoveredArtifactsLoading && (
                                <p className="px-2 py-1 text-sm text-slate-500">
                                    Loading recovered artifacts...
                                </p>
                            )}

                            {!recoveredArtifactsLoading &&
                                recoveredArtifactsError && (
                                    <p className="px-2 py-1 text-sm text-red-600">
                                        {recoveredArtifactsError}
                                    </p>
                                )}

                            {!recoveredArtifactsLoading &&
                                !recoveredArtifactsError &&
                                recoveredArtifacts.length === 0 && (
                                    <p className="px-2 py-1 text-sm text-slate-500">
                                        No recovered artifacts found for this case.
                                    </p>
                                )}

                            {!recoveredArtifactsLoading &&
                                recoveredArtifacts.map((artifact) => (
                                    <div
                                        key={artifact.artifact_id}
                                        role="button"
                                        tabIndex={0}
                                        onClick={() => {
                                            setSelectedRecovered(artifact);
                                            onOpenPreview();
                                        }}
                                        onKeyDown={(event) => {
                                            if (event.key === "Enter") {
                                                setSelectedRecovered(artifact);
                                                onOpenPreview();
                                            }
                                        }}
                                        className={`cursor-pointer rounded px-2 py-2 text-sm hover:bg-slate-50 ${
                                            selectedRecovered?.artifact_id === artifact.artifact_id ? "bg-indigo-50" : ""
                                        }`}
                                        title={`Click to preview · SHA-256: ${artifact.sha256}`}
                                    >
                                        <div className="flex items-start gap-2">
                                            <FileSearch
                                                size={15}
                                                className="mt-0.5 shrink-0 text-indigo-600"
                                            />

                                            <div className="min-w-0">
                                                <div className="break-all font-medium text-slate-800">
                                                    {`${artifact.signature} @ ${artifact.source_offset}.${artifact.extension}`}
                                                </div>

                                                <div className="mt-1 space-y-0.5 break-all text-xs text-slate-500">
                                                    <p>
                                                        Size:{" "}
                                                        {artifact.size.toLocaleString()} bytes
                                                    </p>

                                                    <p>
                                                        Source offset:{" "}
                                                        {artifact.source_offset.toLocaleString()}
                                                    </p>

                                                    <p>
                                                        Region start offset:{" "}
                                                        {artifact.region_start_offset.toLocaleString()}
                                                    </p>

                                                    <p>
                                                        Clusters:{" "}
                                                        {artifact.start_cluster.toLocaleString()}–
                                                        {artifact.end_cluster.toLocaleString()}
                                                    </p>

                                                    <p>
                                                        Confidence:{" "}
                                                        {(artifact.confidence * 100).toFixed(1)}%
                                                    </p>

                                                    {artifact.fragments && (
                                                        <p className="text-amber-700">
                                                            Reassembled from {artifact.fragments.length} fragments
                                                            (lower confidence)
                                                        </p>
                                                    )}

                                                    <p>SHA-256: {artifact.sha256}</p>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                ))}
                        </div>
                    )}
                </div>
            </div>
        </aside>
    );
}
