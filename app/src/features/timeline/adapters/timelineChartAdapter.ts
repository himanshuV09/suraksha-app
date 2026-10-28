import type {
    TimelineGraphPoint,
} from "../types/timeline";


export interface TimelineChartPoint {

    x: string;

    created: number;

    modified: number;

    accessed: number;

    deleted: number;

    mft_modified: number;

}


export class TimelineChartAdapter {

    static adapt(
        graph: TimelineGraphPoint[],
    ): TimelineChartPoint[] {

        return graph.map(
            (point) => ({

                x: point.date,

                created: point.created,

                modified: point.modified,

                accessed: point.accessed,

                deleted: point.deleted,

                mft_modified: point.mft_modified,

            })
        );

    }

}