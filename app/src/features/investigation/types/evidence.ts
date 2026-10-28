export interface EvidenceRecord {

    evidence_id: number;

    case_id: number;

    record_number: number;

    parent_record: number | null;

    filename: string;

    full_path: string | null;

    file_size: number;

    allocated_size: number;

    slack_space: number;

    slack_entropy: number;

    fragment_count: number;

    fragmented: number;

    fragment_ratio: number;

    deleted: number;

    directory: number;

    risk_score: number;

    record_type: string;

}

export interface EvidenceResponse {

    success: boolean;

    case_id: number;

    count: number;

    evidence: EvidenceRecord[];

}