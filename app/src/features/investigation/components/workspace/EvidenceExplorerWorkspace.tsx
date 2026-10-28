import { useState } from "react";
import FileTree from "../tree/FileTree";
import EvidenceTable from "../EvidenceTable";
import PropertiesPanel from "../PropertiesPanel";
import InvestigationPanel from "../investigation/EvidenceInspector";

import ResizeHandle from "./ResizeHandle";

import {
    Panel,
    PanelGroup,
} from "react-resizable-panels";

import type { EvidenceRecord } from "../../types/evidence";
import type { JobProgress } from "../../../../lib/engine";
import type { FilesystemNode } from "../../types/filesystem";
import type { RecoveredArtifact } from "../../types/recovered-artifact";


interface InvestigationWorkspaceProps {
    tree: FilesystemNode | null;
    treeLoading: boolean;

    evidence: EvidenceRecord[];
    loading: boolean;

    recoveredArtifacts: RecoveredArtifact[];
    recoveredArtifactsLoading: boolean;
    recoveredArtifactsError: string | null;
    imagePath: string;
    databasePath: string;
    caseId: number | null;
    onRecoverUnallocated: (imagePath: string, databasePath: string, caseId: number) => Promise<boolean>;
    recoveringUnallocated: boolean;
    recoveryProgress: JobProgress | null;
    onCancelRecovery: () => void;
    recoveryError: string | null;
    recoveryMessage: string | null;
}

export default function EvidenceExplorerWorkspace({
    tree,
    treeLoading,
    evidence,
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
}: InvestigationWorkspaceProps) {

    const [selectedRegionIndex, setSelectedRegionIndex] =
        useState<number | null>(null);

    const [unallocatedTabRequest, setUnallocatedTabRequest] =
        useState(0);

    const openUnallocatedTab = () => {
        setUnallocatedTabRequest((request) => request + 1);
    };

    const [previewTabRequest, setPreviewTabRequest] =
        useState(0);

    const openPreviewTab = () => {
        setPreviewTabRequest((request) => request + 1);
    };

    return (

        <div className="flex h-full min-h-0 flex-1 flex-col overflow-hidden p-4">

            <PanelGroup
                direction="vertical"
                autoSaveId="suraksha-workspace"
                className="h-full"
            >

                {/* ==========================
                    TOP WORKSPACE
                =========================== */}

                <Panel
                    defaultSize={60}
                    minSize={35}
                >

                    <PanelGroup
                        direction="horizontal"
                        autoSaveId="suraksha-investigation-layout"
                        className="h-full"
                    >

                        <Panel
                            defaultSize={20}
                            minSize={15}
                        >
                            <FileTree
                                tree={tree}
                                loading={treeLoading}
                                recoveredArtifacts={recoveredArtifacts}
                                recoveredArtifactsLoading={recoveredArtifactsLoading}
                                recoveredArtifactsError={recoveredArtifactsError}
                                imagePath={imagePath}
                                databasePath={databasePath}
                                caseId={caseId}
                                onRecoverUnallocated={onRecoverUnallocated}
                                recoveringUnallocated={recoveringUnallocated}
                                recoveryProgress={recoveryProgress}
                                onCancelRecovery={onCancelRecovery}
                                recoveryError={recoveryError}
                                recoveryMessage={recoveryMessage}
                                selectedRegionIndex={selectedRegionIndex}
                                onSelectRegion={setSelectedRegionIndex}
                                onOpenUnallocated={openUnallocatedTab}
                                onOpenPreview={openPreviewTab}
                            />
                        </Panel>

                        <ResizeHandle />

                        <Panel
                            defaultSize={55}
                            minSize={30}
                        >
                            <EvidenceTable
                                evidence={evidence}
                                loading={loading}
                            />
                        </Panel>

                        <ResizeHandle />

                        <Panel
                            defaultSize={25}
                            minSize={18}
                        >
                            <PropertiesPanel />
                        </Panel>

                    </PanelGroup>

                </Panel>

                <ResizeHandle />

                {/* ==========================
                    BOTTOM PANEL
                =========================== */}

                <Panel
                    defaultSize={40}
                    minSize={20}
                >

                    <InvestigationPanel 
                        imagePath={imagePath}
                        databasePath={databasePath}
                        caseId={caseId}
                        selectedRegionIndex={selectedRegionIndex}
                        onSelectRegion={setSelectedRegionIndex}
                        unallocatedTabRequest={unallocatedTabRequest}
                        previewTabRequest={previewTabRequest}
                    />

                </Panel>

            </PanelGroup>

        </div>

    );

}