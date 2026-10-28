import { useEffect } from "react";
import type { AnalysisResult } from "../../analyzer/types/analysis-result";
import { useEvidence } from "../hooks/useEvidence";
import { useFilesystemTree } from "../hooks/useFilesystemTree";
import InvestigationWorkspace from "../components/workspace/EvidenceExplorerWorkspace";
import { useInvestigation } from "../context/InvestigationContext";
import InvestigationLayout from "../layout/InvestigationLayout";
import { useRecoveredArtifacts } from "../hooks/useRecoveredArtifacts";

interface InvestigationPageProps {
    analysis: AnalysisResult | null;
}

export default function EvidenceExplorerPage({
    analysis,
}: InvestigationPageProps) {

        const {

            setAnalysis,

            setDatabasePath,

            setCaseId,

        } = useInvestigation();

        const {

            evidence,

            loading,

            error: evidenceError,

            loadEvidence,

        } = useEvidence();

        const {

            tree,

            loading: treeLoading,

            error: treeError,

            loadFilesystemTree,

        } = useFilesystemTree();

        const loadErrors = [evidenceError, treeError].filter(
            (message): message is string => Boolean(message)
        );

        const {
            artifacts: recoveredArtifacts,
            loading: recoveredArtifactsLoading,
            error: recoveredArtifactsError,
            loadRecoveredArtifacts,
            recoverUnallocated,
            recovering,
            recoveryProgress,
            cancelRecovery,
            recoveryError,
            recoveryMessage,
        } = useRecoveredArtifacts();

            useEffect(() => {

        if (!analysis) {

            return;

        }

        // The engine reports where it stored the case; never guess it.
        const databasePath = analysis.database_path;

        const caseId = analysis.case_id;

        // Save investigation information into the global context
        setAnalysis(analysis);
        setDatabasePath(databasePath);
        setCaseId(caseId);

        loadEvidence(

            databasePath,

            caseId

        );

        loadFilesystemTree(
            databasePath,
            caseId
        );

        loadRecoveredArtifacts(databasePath, caseId);
        

    }, [

        analysis,

        loadEvidence,

        loadFilesystemTree,

        loadRecoveredArtifacts,

        setAnalysis,

        setDatabasePath,
        
        setCaseId,

    ]);

    return (

        <div className="flex h-full min-h-0 flex-1 flex-col bg-slate-100 overflow-hidden">

                {loadErrors.length > 0 && (
                    <div
                        role="alert"
                        className="border-b border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700"
                    >
                        {loadErrors.map((message) => (
                            <p key={message}>{message}</p>
                        ))}
                    </div>
                )}

                <InvestigationLayout>
                    <InvestigationWorkspace
                        tree={tree}
                        treeLoading={treeLoading}
                        evidence={evidence}
                        loading={loading}
                        recoveredArtifacts={recoveredArtifacts}
                        recoveredArtifactsLoading={recoveredArtifactsLoading}
                        recoveredArtifactsError={recoveredArtifactsError}
                        imagePath={analysis?.image_path ?? ""}
                        databasePath={analysis?.database_path ?? ""}
                        caseId={analysis?.case_id ?? null}
                        onRecoverUnallocated={recoverUnallocated}
                        recoveringUnallocated={recovering}
                        recoveryProgress={recoveryProgress}
                        onCancelRecovery={cancelRecovery}
                        recoveryError={recoveryError}
                        recoveryMessage={recoveryMessage}
                    />
                </InvestigationLayout>

        </div>

    );
}