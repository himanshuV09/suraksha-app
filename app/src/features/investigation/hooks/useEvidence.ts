import { useCallback, useState } from "react";

import { errorMessage } from "../../../lib/engine";

import { useInvestigation,} from "../context/InvestigationContext";

import { investigationService }
    from "../services/investigation.service";

import type {
    EvidenceRecord,
} from "../types/evidence";

export function useEvidence() {

    const {

        // databasePath,

        setDatabasePath,

        // caseId,

        setCaseId,
        
        evidence,

        setEvidence,

        setSelectedEvidence,

        setSelectedPreview,

    } = useInvestigation();
        

    const [loading, setLoading] =
        useState(false);

    const [error, setError] =
        useState<string | null>(null);

    const loadEvidence =
        useCallback(

        async (

            databasePath: string,

            caseId: number

        ) => {

            setLoading(true);
            setError(null);

            try {

                const response =
                    await investigationService.loadEvidence(
                        databasePath,
                        caseId
                    );
                
                setDatabasePath(databasePath);
                setCaseId(caseId);

                setEvidence(response.evidence);
                setSelectedEvidence(null);
                setSelectedPreview(null);

            }

            catch (err) {

                setEvidence([]);
                setError(errorMessage(err));

            }

            finally {

                setLoading(false);

            }

        },

        [
            setDatabasePath,
            setCaseId,
            setEvidence,
            setSelectedEvidence,
            setSelectedPreview,
        ]

    );

    const selectRecord =
    useCallback(

        (
            record: EvidenceRecord
        ) => {


            setSelectedEvidence(record);

            setSelectedPreview({
                evidence: record,
            });

        },

        [
            setSelectedEvidence,
            setSelectedPreview]

    );

    return {

        evidence,

        loading,

        error,

        loadEvidence,

        selectRecord,

    };

}