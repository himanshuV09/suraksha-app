import { useQuery } from "@tanstack/react-query";

import { timelineApi } from "../api/timelineApi";

export interface UseTimelineOptions {
    databasePath: string;
    caseId: number | null;
    interval?: "day" | "week" | "month" | "year";
    recordNumber?: number;
}

export function useTimeline({
    databasePath,
    caseId,
    interval = "day",
    recordNumber,
}: UseTimelineOptions) {
    return useQuery({
        queryKey: [
            "timeline",
            databasePath,
            caseId,
            interval,
            recordNumber,
        ],

        queryFn: () =>
            timelineApi.getGraph({
                databasePath,
                caseId: caseId!,
                interval,
                recordNumber,
            }),

        enabled:
            databasePath.length > 0 &&
            caseId !== null &&
            recordNumber !== undefined,

        staleTime: 1000 * 60 * 5,
    });
}