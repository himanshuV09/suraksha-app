import { useEffect, useState } from "react";

import { errorMessage } from "../../../lib/engine";
import { useInvestigation } from "../context/InvestigationContext";
import { investigationService } from "../services/investigation.service";
import type { PreviewResult } from "../types/preview";

export interface PreviewState extends PreviewResult {
    /** Set for carved files: does the image still match the stored hash? */
    hash_verified?: boolean;
}

/**
 * Loads the preview for whatever is selected: a file, a member of a
 * container file, or a file carved from free space.
 */
export function usePreview() {

    const {
        analysis,
        databasePath,
        caseId,
        selectedPreview,
        selectedRecovered,
    } = useInvestigation();

    const [preview, setPreview] = useState<PreviewState | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {

        if (!selectedPreview && !selectedRecovered) {
            setPreview(null);
            setError(null);
            setLoading(false);
            return;
        }

        if (!databasePath) {
            setPreview(null);
            setError("No investigation database loaded.");
            setLoading(false);
            return;
        }

        let cancelled = false;

        async function loadPreview() {
            setLoading(true);
            setError(null);
            setPreview(null);
            try {
                let result: PreviewState;
                if (selectedRecovered) {
                    if (!analysis?.image_path || caseId === null) {
                        throw new Error("The evidence image of this case is not known.");
                    }
                    result = await investigationService.previewRecovered(
                        analysis.image_path,
                        databasePath,
                        caseId,
                        selectedRecovered.artifact_id,
                    );
                } else {
                    result = await investigationService.loadPreview(
                        databasePath,
                        selectedPreview!.evidence.evidence_id,
                        selectedPreview!.artifact?.path,
                    );
                }
                if (!cancelled) {
                    setPreview(result);
                }
            } catch (err) {
                if (!cancelled) {
                    setError(errorMessage(err));
                    setPreview(null);
                }
            } finally {
                if (!cancelled) {
                    setLoading(false);
                }
            }
        }

        void loadPreview();

        return () => {
            cancelled = true;
        };

    }, [analysis, databasePath, caseId, selectedPreview, selectedRecovered]);

    return {
        selectedPreview,
        selectedRecovered,
        preview,
        loading,
        error,
    };
}
