export type TimelineInterval =
    | "day"
    | "week"
    | "month"
    | "year";


export interface TimelineSummary {

    total_events: number;

    created: number;

    modified: number;

    accessed: number;

    deleted: number;

    mft_modified: number;

    first_event: string | null;

    last_event: string | null;

    most_active_day: string | null;
}


export interface TimelineGraphPoint {

    date: string;

    created: number;

    modified: number;

    accessed: number;

    deleted: number;

    mft_modified: number;
}


export interface TimelineEvent {

    record_number: number;

    timestamp: string | null;

    event_type: string;

    filename: string;

    full_path: string;

    source: string;

    artifact_type: string;

    deleted: boolean;

    directory: boolean;

    description: string;
}


export interface TimelineResponse {

    success: boolean;

    case_id: number;

    summary: TimelineSummary;

    graph: TimelineGraphPoint[];

    events: TimelineEvent[];
}