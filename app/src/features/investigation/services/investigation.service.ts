import { callEngine } from "../../../lib/engine";

import type {
    EvidenceResponse,
} from "../types/evidence";

import type {
    FilesystemResponse,
} from "../types/filesystem"

import type { PreviewResult } from "../types/preview";

import type {
    RecoveredArtifactsResponse,
} from "../types/recovered-artifact";

export interface UnallocatedRecoveryResponse {
    success?: boolean;
    case_id?: number;
    count?: number;
    recovered_count?: number;
    message?: string;
    error?: string;
    [key: string]: unknown;
}

/**
 * Engine calls for the investigation workspace.
 *
 * Every method resolves with the engine's result or rejects with an
 * Error carrying the engine's message; see lib/engine.ts.
 */
class InvestigationService {

    loadEvidence(
        databasePath: string,
        caseId: number
    ): Promise<EvidenceResponse> {
        return callEngine("get_evidence", { databasePath, caseId });
    }

    loadRecoveredArtifacts(
        databasePath: string,
        caseId: number
    ): Promise<RecoveredArtifactsResponse> {
        return callEngine("get_recovered_artifacts", { databasePath, caseId });
    }

    recoverUnallocated(
        imagePath: string,
        databasePath: string,
        caseId: number
    ): Promise<UnallocatedRecoveryResponse> {
        return callEngine("recover_unallocated", {
            imagePath,
            databasePath,
            caseId,
        });
    }

    /** Bytes between a file's end and the end of its clusters. */
    loadFileSlack(
        databasePath: string,
        evidenceId: number
    ): Promise<{
        filename: string;
        file_size: number;
        resident: boolean;
        slack_size: number;
        slack_offset: number | null;
        truncated: boolean;
        all_zero: boolean;
        data: string;
        strings: string[];
    }> {
        return callEngine("get_file_slack", { databasePath, evidenceId });
    }

    /** Preview a file carved from free space (hash re-checked). */
    previewRecovered(
        imagePath: string,
        databasePath: string,
        caseId: number,
        artifactId: number
    ): Promise<PreviewResult & { hash_verified?: boolean; sha256?: string }> {
        return callEngine("preview_recovered", {
            imagePath,
            databasePath,
            caseId,
            artifactId,
        });
    }

    /** Write carved files to a folder with a SHA-256 manifest. */
    exportRecovered(
        imagePath: string,
        databasePath: string,
        caseId: number,
        destination: string,
        artifactIds?: number[]
    ): Promise<{
        destination: string;
        manifest: string;
        exported_count: number;
        failed_count: number;
        hash_mismatches: number;
    }> {
        return callEngine("export_recovered", {
            imagePath,
            databasePath,
            caseId,
            destination,
            artifactIds: artifactIds ?? null,
        });
    }

    loadFilesystemTree(
        databasePath: string,
        caseId: number
    ): Promise<FilesystemResponse> {
        return callEngine("get_filesystem_tree", { databasePath, caseId });
    }

    loadPreview(
        databasePath: string,
        evidenceId: number,
        artifactPath?: string
    ): Promise<PreviewResult> {
        return callEngine("get_preview", {
            databasePath,
            evidenceId,
            artifactPath,
        });
    }

}

export const investigationService =
    new InvestigationService();
