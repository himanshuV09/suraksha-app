import { useCallback, useState } from "react";

import { useJob } from "../../../hooks/useJob";
import { errorMessage } from "../../../lib/engine";
import { investigationService, type UnallocatedRecoveryResponse } from "../services/investigation.service";

import type { RecoveredArtifact } from "../types/recovered-artifact";

export function useRecoveredArtifacts() {
    const [artifacts, setArtifacts] = useState<RecoveredArtifact[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [recoveryMessage, setRecoveryMessage] = useState<string | null>(null);
    const recovery = useJob<UnallocatedRecoveryResponse>("recover");

    const loadRecoveredArtifacts = useCallback(
        async (databasePath: string, caseId: number) => {
            setLoading(true);
            setError(null);
            try {
                const response = await investigationService.loadRecoveredArtifacts(databasePath, caseId);
                setArtifacts(response.artifacts);
                return true;
            } catch (err: unknown) {
                setArtifacts([]);
                setError(errorMessage(err));
                return false;
            } finally {
                setLoading(false);
            }
        },
        []
    );

    const { run: runRecovery } = recovery;

    /** Scan free space for files (long-running; reports progress). */
    const recoverUnallocated = useCallback(
        async (imagePath: string, databasePath: string, caseId: number) => {
            setRecoveryMessage(null);
            const response = await runRecovery("recover_unallocated", {
                imagePath,
                databasePath,
                caseId,
            });
            if (!response) {
                return false;
            }
            await loadRecoveredArtifacts(databasePath, caseId);
            const fragmented = Number(response.recovered_fragmented ?? 0);
            setRecoveryMessage(
                `Recovery finished: ${response.recovered_count ?? 0} file(s) recovered` +
                (fragmented ? `, ${fragmented} reassembled from fragments` : "") + "."
            );
            return true;
        },
        [loadRecoveredArtifacts, runRecovery]
    );

    return {
        artifacts,
        loading,
        error,
        loadRecoveredArtifacts,
        recoverUnallocated,
        recovering: recovery.running,
        recoveryProgress: recovery.progress,
        cancelRecovery: recovery.cancel,
        recoveryError: recovery.status === "cancelled" ? "Recovery cancelled." : recovery.error,
        recoveryMessage,
    };
}
