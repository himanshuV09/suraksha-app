import { useEffect, useState } from "react";
import MetadataTab from "./tabs/MetadataTab";
import PreviewTab from "../../preview/PreviewTab";
import UnallocatedSpaceTab from "./tabs/UnallocatedSpaceTab";
import MetafilesTab from "./tabs/MetafilesTab";
import DeletedFilesTab from "./tabs/DeletedFilesTab";
import SlackTab from "./tabs/SlackTab";

const tabs = [
    "Metadata",
    "Preview",
    "Hex",
    "Unallocated",
    "Slack",
    "Deleted Files",
    "Metafiles",
    "ADS",
    "Container",
    "Hashes",
    "AI",
];

interface EvidenceInspectorProps {
    imagePath: string;
    databasePath: string;
    caseId: number | null;
    selectedRegionIndex: number | null;
    onSelectRegion: (index: number | null) => void;
    unallocatedTabRequest: number;
    previewTabRequest: number;
}

export default function EvidenceInspector({
    imagePath,
    databasePath,
    caseId,
    selectedRegionIndex,
    onSelectRegion,
    unallocatedTabRequest,
    previewTabRequest,
}: EvidenceInspectorProps) {
    const [activeTab, setActiveTab] = useState("Metadata");

    useEffect(() => {
        if (unallocatedTabRequest > 0) {
            setActiveTab("Unallocated");
        }
    }, [unallocatedTabRequest]);

    useEffect(() => {
        if (previewTabRequest > 0) {
            setActiveTab("Preview");
        }
    }, [previewTabRequest]);

    

    return (

        <section className="flex h-full flex-col rounded-lg border bg-white shadow-sm">

            {/* Tab Bar */}
            <div className="flex overflow-x-auto border-b">

                {tabs.map((tab) => (
                    <button
                        key={tab}
                        onClick={() => 
                            setActiveTab(tab)}
                        className={`border-r px-4 py-2 text-sm font-medium transition-colors ${
                            activeTab === tab
                                ? "bg-indigo-50 text-indigo-600 border-b-2 border-indigo-600"
                                : "text-slate-600 hover:bg-slate-100"
                        }`}
                    >
                        {tab}
                    </button>
                ))}

            </div>

            {/* Content */}
            <div className="flex-1 min-h-0 overflow-hidden">

                {activeTab === "Metadata" && <MetadataTab />}

                {activeTab === "Unallocated" && (
                    <UnallocatedSpaceTab
                        imagePath={imagePath}
                        databasePath={databasePath}
                        caseId={caseId}
                        selectedRegionIndex={selectedRegionIndex}
                        onSelectRegion={onSelectRegion}
                    />
                )}

                {activeTab === "Slack" && <SlackTab />}

                {activeTab === "Deleted Files" && (
                    <DeletedFilesTab
                        imagePath={imagePath}
                        databasePath={databasePath}
                        caseId={caseId}
                    />
                )}

                {activeTab === "Metafiles" && (
                    <MetafilesTab
                        imagePath={imagePath}
                        databasePath={databasePath}
                        caseId={caseId}
                    />
                )}

                {activeTab === "Preview" && (
                    <div className="h-full w-full">
                        <PreviewTab />
                    </div>
                )}

                {activeTab === "Hex" && (
                    <div className="flex h-full items-center justify-center text-slate-400">
                        Hex Viewer Coming Soon
                    </div>
                )}

                {activeTab === "ADS" && (
                    <div className="flex h-full items-center justify-center text-slate-400">
                        ADS Viewer Coming Soon
                    </div>
                )}

                {activeTab === "Container" && (
                    <div className="flex h-full items-center justify-center text-slate-400">
                        Container Viewer Coming Soon
                    </div>
                )}

                {activeTab === "Hashes" && (
                    <div className="flex h-full items-center justify-center text-slate-400">
                        Hashes Viewer Coming Soon
                    </div>
                )}

                {activeTab === "AI" && (
                    <div className="flex h-full items-center justify-center text-slate-400">
                        AI Investigation Coming Soon
                    </div>
                )}

            </div>

        </section>
    );
}