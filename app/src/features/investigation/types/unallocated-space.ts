export interface UnallocatedRegion {
    index: number;
    start_cluster: number;
    end_cluster: number;
    cluster_count: number;
    start_offset: number;
    end_offset: number;
    byte_count: number;
    state: string;
}

export interface UnallocatedRegionsResponse {
    success: boolean;
    case_id: number;
    region_count: number;
    regions: UnallocatedRegion[];
    error?: string;
}

export interface UnallocatedRawReadResponse {
    success: boolean;
    case_id: number;
    region_index: number;
    region_offset: number;
    absolute_offset: number;
    size: number;
    encoding: "hex";
    data: string;
    error?: string;
}