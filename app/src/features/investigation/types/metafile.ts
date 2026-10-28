/** One NTFS system metafile, as stored by the engine's `metafiles` command. */
export interface Metafile {
    record_number: number;
    name: string;
    status: "ok" | "missing" | "error";
    in_use: boolean | null;
    size: number;
    allocated_size: number;
    resident: boolean | null;
    fragments: number;
    streams: { name: string; size: number; resident: boolean }[];
    created: string | null;
    modified: string | null;
    /** Metafile-specific facts, e.g. $Volume label or $UsnJrnl record count. */
    details: Record<string, unknown>;
    error: string | null;
}

export interface MetafilesResponse {
    success: boolean;
    case_id: number;
    count: number;
    metafiles: Metafile[];
}

export interface ExtractedMetafile {
    name: string;
    record_number: number;
    path?: string;
    size?: number;
    skipped?: string;
    error?: string;
}

export interface ExtractMetafilesResponse {
    success: boolean;
    destination: string;
    exported_count: number;
    /** Streams with no data on disk (e.g. $BadClus:$Bad), not written. */
    skipped_count: number;
    failed_count: number;
    files: ExtractedMetafile[];
}
