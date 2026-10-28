import { invoke } from "@tauri-apps/api/core";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";

/**
 * Call a forensic engine command through the Tauri backend.
 *
 * The backend returns the engine's JSON result as an object. When the
 * engine fails, the promise rejects with an Error whose message is the
 * engine's own explanation (for example "Case database not found: ...").
 */
export async function callEngine<T>(
    command: string,
    args: Record<string, unknown> = {},
): Promise<T> {
    try {
        return await invoke<T>(command, args);
    } catch (error) {
        throw new Error(errorMessage(error));
    }
}

/** A readable message from anything thrown by invoke or a service. */
export function errorMessage(error: unknown): string {
    if (error instanceof Error) {
        return error.message;
    }
    if (typeof error === "string" && error.trim()) {
        return error;
    }
    return "The forensic engine returned an unknown error.";
}

/** The engine reports this message when a job was stopped by the user. */
export const CANCELLED = "Cancelled.";

export function isCancelled(error: unknown): boolean {
    return errorMessage(error) === CANCELLED;
}

// ----------------------------------------------------------------------
// Long-running jobs: progress and cancellation
// ----------------------------------------------------------------------

export interface JobProgress {
    jobId: string;
    stage: string;
    done: number | null;
    total: number | null;
    message: string;
}

export function newJobId(prefix = "job"): string {
    return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

/** Receive progress reports for one job; returns an unsubscribe function. */
export function onJobProgress(
    jobId: string,
    handler: (progress: JobProgress) => void,
): Promise<UnlistenFn> {
    return listen<JobProgress>("engine-progress", (event) => {
        if (event.payload.jobId === jobId) {
            handler(event.payload);
        }
    });
}

/** Ask the backend to stop a running job. */
export function cancelJob(jobId: string): Promise<boolean> {
    return invoke<boolean>("cancel_job", { jobId });
}

/**
 * Run a long engine command with progress reporting.
 *
 * `onProgress` receives every report until the command finishes.
 */
export async function runJob<T>(
    command: string,
    args: Record<string, unknown>,
    jobId: string,
    onProgress: (progress: JobProgress) => void,
): Promise<T> {
    const unlisten = await onJobProgress(jobId, onProgress);
    try {
        return await callEngine<T>(command, { ...args, jobId });
    } finally {
        unlisten();
    }
}
