import { useCallback, useState } from "react";

import { errorMessage } from "../../../lib/engine";

import { investigationService }
    from "../services/investigation.service";

import type {
    FilesystemNode,
} from "../types/filesystem";

export function useFilesystemTree() {

    const [tree, setTree] =
        useState<FilesystemNode | null>(null);

    const [loading, setLoading] =
        useState(false);

    const [error, setError] =
        useState<string | null>(null);

    const loadFilesystemTree =
        useCallback(

            async (

                databasePath: string,

                caseId: number

            ) => {

                setLoading(true);
                setError(null);

                try {

                    const response =
                        await investigationService.loadFilesystemTree(
                            databasePath,
                            caseId
                        );

                    setTree(response.tree);

                }

                catch (err) {

                    setTree(null);
                    setError(errorMessage(err));

                }

                finally {

                    setLoading(false);

                }

            },

            []

        );

    return {

        tree,

        loading,

        error,

        loadFilesystemTree,

    };

}
