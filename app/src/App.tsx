import "./App.css";

import { useState, type ReactNode } from "react";

import Sidebar from "./components/layout/Sidebar";
import ErrorBoundary from "./components/shared/ErrorBoundary";

import AnalyzerPage from "./features/analyzer/AnalyzerPage";
import CasesPage from "./features/cases/CasesPage";
import EvidenceExplorerPage from "./features/investigation/pages/EvidenceExplorerPage";
import TimelinePage from "./features/timeline/pages/TimelinePage";

import type { AppPage } from "./types/navigation";
import type { AnalysisResult } from "./features/analyzer/types/analysis-result";
import type { CaseSummary } from "./features/cases/types";

import { InvestigationProvider } from "./features/investigation/context/InvestigationContext";

/** The active case when it is opened from the Cases page. */
function caseToAnalysis(summary: CaseSummary): AnalysisResult {
    return {
        success: true,
        message: "",
        case_id: summary.case_id,
        case_name: summary.case_name,
        investigator: summary.investigator ?? "",
        image_path: summary.image_path ?? "",
        database_path: summary.database_path,
        filesystem: "NTFS",
        volume_label: "",
        serial_number: "",
        image_size: 0,
        cluster_size: 0,
        sector_size: 0,
        total_records: summary.evidence_count,
        total_files: 0,
        total_directories: 0,
        deleted_files: 0,
        fragmented_files: 0,
        fragment_count: 0,
        ads_files: 0,
        slack_files: 0,
        high_risk_files: 0,
        timeline_events: 0,
        corrupt_records: 0,
        record_error_count: 0,
        record_errors: [],
        warnings: [],
        metafile_counts: {},
        deleted_recovery: {},
        duration: 0,
        errors: [],
    };
}

function App() {

    const [currentPage, setCurrentPage] = useState<AppPage>("cases");
    const [activeCase, setActiveCase] = useState<AnalysisResult | null>(null);

    const pages: Record<AppPage, ReactNode> = {
        cases: (
            <CasesPage
                onOpenCase={(summary) => {
                    setActiveCase(caseToAnalysis(summary));
                    setCurrentPage("investigation");
                }}
                onNewAnalysis={() => setCurrentPage("analyzer")}
            />
        ),
        analyzer: (
            <AnalyzerPage
                onAnalysisCompleted={setActiveCase}
                onOpenInvestigation={() => setCurrentPage("investigation")}
            />
        ),
        investigation: <EvidenceExplorerPage analysis={activeCase} />,
        timeline: <TimelinePage />,
    };

    return (
        <InvestigationProvider>
            <div className="flex h-screen bg-slate-50">
                <Sidebar
                    currentPage={currentPage}
                    onNavigate={setCurrentPage}
                    caseOpen={activeCase !== null}
                    caseName={activeCase?.case_name}
                />
                <main className="flex-1 overflow-y-auto">
                    {/* Keyed by page, so an error on one page does not lock the app. */}
                    <ErrorBoundary key={currentPage}>
                        {pages[currentPage]}
                    </ErrorBoundary>
                </main>
            </div>
        </InvestigationProvider>
    );
}

export default App;
