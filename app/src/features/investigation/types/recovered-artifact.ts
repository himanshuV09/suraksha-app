export interface RecoveredArtifact {
    artifact_id: number;
    signature: string;
    extension: string;
    size: number;
    sha256: string;
    confidence: number;
    source_image: string;
    source_type: string;
    region_start_cluster: number;
    region_end_cluster: number;
    region_start_offset: number;
    source_offset: number;
    relative_offset: number;
    start_cluster: number;
    end_cluster: number;
    validation_reason: string;
    /** [absolute_offset, length] per piece for files reassembled from
     *  several free-space fragments; null for contiguous files. */
    fragments: [number, number][] | null;
}

export interface RecoveredArtifactsResponse {
    success: boolean;
    case_id: number;
    count: number;
    artifacts: RecoveredArtifact[];
}