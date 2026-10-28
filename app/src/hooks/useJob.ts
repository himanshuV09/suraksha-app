import { useCallback, useRef, useState } from "react";

import {
    cancelJob,
    errorMessage,
    isCancelled,
    newJobId,
    runJob,
    type JobProgress,
} from "../lib/engine";

export type JobStatus = "idle" | "running" | "done" | "failed" | "cancelled";

/**
 * State for one long engine command: progress, result, error, cancel.
 *
 *   const job = useJob<RecoveryResult>();
 *   await job.run("recover_unallocated", { imagePath, ... });
 */
export function useJob<T>(prefix = "job") {
    const [status, setStatus] = useState<JobStatus>("idle");
    const [progress, setProgress] = useState<JobProgress | null>(null);
    const [error, setError] = useState<string | null>(null);
    const jobId = useRef<string | null>(null);

    const run = useCallback(async (command: string, args: Record<string, unknown>): Promise<T | null> => {
        const id = newJobId(prefix);
        jobId.current = id;
        setStatus("running");
        setProgress(null);
        setError(null);
        try {
            const result = await runJob<T>(command, args, id, setProgress);
            setStatus("done");
            return result;
        } catch (err) {
            if (isCancelled(err)) {
                setStatus("cancelled");
            } else {
                setStatus("failed");
                setError(errorMessage(err));
            }
            return null;
        } finally {
            jobId.current = null;
        }
    }, [prefix]);

    const cancel = useCallback(async () => {
        if (jobId.current) {
            await cancelJob(jobId.current);
        }
    }, []);

    const reset = useCallback(() => {
        setStatus("idle");
        setProgress(null);
        setError(null);
    }, []);

    return { status, running: status === "running", progress, error, run, cancel, reset };
}
