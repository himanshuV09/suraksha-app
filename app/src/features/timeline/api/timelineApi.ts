/**
 * Timeline API.
 *
 * Provides communication between the React frontend
 * and the forensic backend.
 */

import { callEngine } from "../../../lib/engine";

import type {
    TimelineResponse,
} from "../types/timeline";


export interface TimelineGraphRequest {

    databasePath: string;

    caseId: number;

    interval?: "day" | "week" | "month" | "year";

    recordNumber?: number;

}


export class TimelineApi {

    /**
     * Retrieve timeline data.
     *
     * Returns:
     *
     * summary → investigation statistics
     * graph   → aggregated timeline data
     * events  → raw forensic events
     */
    getGraph(
        request: TimelineGraphRequest,
    ): Promise<TimelineResponse> {
        return callEngine<TimelineResponse>("get_timeline_graph", {
            databasePath: request.databasePath,
            caseId: request.caseId,
            interval: request.interval ?? "day",
            recordNumber: request.recordNumber,
        });
    }

}


/**
 * Singleton instance.
 */
export const timelineApi =
    new TimelineApi();