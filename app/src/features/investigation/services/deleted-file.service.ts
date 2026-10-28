import { callEngine } from "../../../lib/engine";

import type {
    DeletedFilesResponse,
    DeletedFileStatus,
    RecoverDeletedResponse,
} from "../types/deleted-file";

class DeletedFileService {
    load(databasePath: string, caseId: number): Promise<DeletedFilesResponse> {
        return callEngine("get_deleted_files", { databasePath, caseId });
    }

    /** Restore files under their original paths inside `destination`. */
    recover(
        imagePath: string,
        databasePath: string,
        caseId: number,
        destination: string,
        options: { statuses?: DeletedFileStatus[]; recordNumbers?: number[] } = {},
    ): Promise<RecoverDeletedResponse> {
        return callEngine("recover_deleted", {
            imagePath,
            databasePath,
            caseId,
            destination,
            statuses: options.statuses ?? null,
            recordNumbers: options.recordNumbers ?? null,
        });
    }
}

export const deletedFileService = new DeletedFileService();
