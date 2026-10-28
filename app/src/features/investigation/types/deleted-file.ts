export type DeletedFileStatus = "recoverable" | "partial" | "overwritten" | "no_data";

/** A deleted file still described in the MFT, graded during analysis. */
export interface DeletedFile {
    record_number: number;
    sequence_number: number | null;
    filename: string;
    full_path: string;
    file_size: number;
    resident: boolean;
    status: DeletedFileStatus;
    total_clusters: number;
    free_clusters: number;
    reused_clusters: number;
    recoverable_bytes: number;
    recoverable_percent: number;
    /** Files that now occupy some of this file's old clusters. */
    overwritten_by: string[];
    /** [start, end) byte offsets that hold other data now. */
    unreliable_ranges: [number, number][];
    /** "verified" | "header_ok" | "mismatch" | "unknown" */
    content_check: string;
    created: string | null;
    modified: string | null;
    accessed: string | null;
    mft_modified: string | null;
}

export interface DeletedFilesResponse {
    success: boolean;
    case_id: number;
    count: number;
    status_counts: Record<DeletedFileStatus, number>;
    files: DeletedFile[];
}

export interface RecoverDeletedResponse {
    success: boolean;
    destination: string;
    manifest: string;
    recovered_count: number;
    failed_count: number;
    recovered_bytes: number;
    files: {
        record_number: number;
        original_path: string;
        status: DeletedFileStatus;
        path?: string;
        sha256?: string;
        error?: string;
    }[];
}
