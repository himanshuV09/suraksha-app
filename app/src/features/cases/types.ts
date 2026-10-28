/** One analysis case, as listed by the engine's `list-cases` command. */
export interface CaseSummary {
    case_id: number;
    case_name: string;
    image_path: string | null;
    created_at: string | null;
    investigator: string | null;
    description: string | null;
    /** "running" while being analyzed; left "running" if interrupted. */
    status: "complete" | "failed" | "running" | "unknown";
    engine_version: string | null;
    completed_at: string | null;
    evidence_count: number;
    database_path: string;
    image_available: boolean;
}

export interface CasesResponse {
    success: boolean;
    cases_dir: string;
    count: number;
    cases: CaseSummary[];
    unreadable: { database_path: string; error: string }[];
}

export interface EngineInfo {
    engine_version: string;
    app_version: string;
    python_version: string;
    frozen: boolean;
    cases_dir: string;
    engine: string;
    log_file: string | null;
}
