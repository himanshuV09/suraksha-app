import { callEngine } from "../../../lib/engine";

import type {
    ExtractMetafilesResponse,
    MetafilesResponse,
} from "../types/metafile";

class MetafileService {
    /** The metafile summary stored when the case was analyzed. */
    load(databasePath: string, caseId: number): Promise<MetafilesResponse> {
        return callEngine("get_metafiles", { databasePath, caseId });
    }

    /** Copy every metafile's raw streams into `destination`. */
    extract(
        imagePath: string,
        databasePath: string,
        caseId: number,
        destination: string,
    ): Promise<ExtractMetafilesResponse> {
        return callEngine("extract_metafiles", {
            imagePath,
            databasePath,
            caseId,
            destination,
        });
    }
}

export const metafileService = new MetafileService();
