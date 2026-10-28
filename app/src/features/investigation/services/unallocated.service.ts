import { callEngine } from "../../../lib/engine";

import type {
    UnallocatedRegionsResponse,
    UnallocatedRawReadResponse,
} from "../types/unallocated-space";

/** Largest raw read the engine accepts in one request. */
export const MAX_RAW_READ_SIZE = 65536;

class UnallocatedSpaceService {
    loadRegions(
        imagePath: string,
        databasePath: string,
        caseId: number,
    ): Promise<UnallocatedRegionsResponse> {
        return callEngine("get_unallocated_regions", {
            imagePath,
            databasePath,
            caseId,
        });
    }

    async readRegion(
        imagePath: string,
        databasePath: string,
        caseId: number,
        regionIndex: number,
        offset: number,
        size: number,
    ): Promise<UnallocatedRawReadResponse> {
        if (!Number.isSafeInteger(offset) || offset < 0) {
            throw new Error("Offset must be a non-negative safe integer.");
        }

        if (!Number.isInteger(size) || size < 1 || size > MAX_RAW_READ_SIZE) {
            throw new Error(
                `Read size must be between 1 and ${MAX_RAW_READ_SIZE} bytes.`,
            );
        }

        const result = await callEngine<UnallocatedRawReadResponse>(
            "read_unallocated_region",
            {
                imagePath,
                databasePath,
                caseId,
                regionIndex,
                offset,
                size,
            },
        );

        if (
            result.encoding !== "hex" ||
            !/^(?:[0-9a-fA-F]{2})*$/.test(result.data) ||
            result.data.length !== result.size * 2 ||
            result.size !== size
        ) {
            throw new Error(
                "The forensic engine returned an invalid raw-byte response.",
            );
        }

        return result;
    }
}

export const unallocatedSpaceService =
    new UnallocatedSpaceService();
