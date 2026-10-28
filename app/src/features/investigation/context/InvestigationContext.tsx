import {
    createContext,
    useCallback,
    useContext,
    useState,
    type ReactNode,
} from "react";

import type { AnalysisResult } from "../../analyzer/types/analysis-result";
import type { EvidenceRecord } from "../types/evidence";
import type { PreviewTarget } from "../types/preview-target";
import type { RecoveredArtifact } from "../types/recovered-artifact";


interface InvestigationContextType {

    analysis: AnalysisResult | null;

    setAnalysis: (
        analysis: AnalysisResult
    ) => void;


    databasePath: string;

    setDatabasePath: (
        path: string
    ) => void;


    caseId: number | null;

    setCaseId: (
        id: number | null
    ) => void;


    evidence: EvidenceRecord[];

    setEvidence: (
        evidence: EvidenceRecord[]
    ) => void;


    selectedEvidence: EvidenceRecord | null;

    setSelectedEvidence: (
        evidence: EvidenceRecord | null
    ) => void;


    selectedPreview: PreviewTarget | null;

    setSelectedPreview: (
        preview: PreviewTarget | null
    ) => void;


    /** A file carved from free space, chosen for preview. */
    selectedRecovered: RecoveredArtifact | null;

    setSelectedRecovered: (
        artifact: RecoveredArtifact | null
    ) => void;

}


const InvestigationContext =
    createContext<InvestigationContextType | null>(
        null
    );


export function InvestigationProvider({

    children,

}: {

    children: ReactNode;

}) {


    // --------------------------------------------------
    // Investigation
    // --------------------------------------------------

    const [

        analysis,

        setAnalysis,

    ] = useState<AnalysisResult | null>(
        null
    );


    const [

        databasePath,

        setDatabasePath,

    ] = useState<string>(
        ""
    );


    const [

        caseId,

        setCaseId,

    ] = useState<number | null>(
        null
    );


    // --------------------------------------------------
    // Evidence
    // --------------------------------------------------

    const [

        evidence,

        setEvidence,

    ] = useState<EvidenceRecord[]>(
        []
    );


    const [

        selectedEvidence,

        setSelectedEvidence,

    ] = useState<EvidenceRecord | null>(
        null
    );


    // --------------------------------------------------
    // Preview
    // --------------------------------------------------

    const [

        selectedPreview,

        setSelectedPreview,

    ] = useState<PreviewTarget | null>(
        null
    );

    const [
        selectedRecovered,
        setSelectedRecoveredState,
    ] = useState<RecoveredArtifact | null>(null);

    // One preview at a time: choosing a file clears a chosen carved
    // artifact and vice versa.
    const selectPreview = useCallback((preview: PreviewTarget | null) => {
        setSelectedPreview(preview);
        if (preview) {
            setSelectedRecoveredState(null);
        }
    }, []);

    const selectRecovered = useCallback((artifact: RecoveredArtifact | null) => {
        setSelectedRecoveredState(artifact);
        if (artifact) {
            setSelectedPreview(null);
        }
    }, []);


    // --------------------------------------------------
    // Context
    // --------------------------------------------------

    return (

        <InvestigationContext.Provider
            value={{

                // Investigation

                analysis,

                setAnalysis,


                databasePath,

                setDatabasePath,


                caseId,

                setCaseId,


                // Evidence

                evidence,

                setEvidence,


                selectedEvidence,

                setSelectedEvidence,


                // Preview

                selectedPreview,

                setSelectedPreview: selectPreview,

                selectedRecovered,

                setSelectedRecovered: selectRecovered,

            }}
        >

            {children}

        </InvestigationContext.Provider>

    );

}


// ------------------------------------------------------
// Hook
// ------------------------------------------------------

export function useInvestigation() {

    const context =
        useContext(
            InvestigationContext
        );


    if (!context) {

        throw new Error(
            "useInvestigation must be used inside InvestigationProvider"
        );

    }


    return context;

}