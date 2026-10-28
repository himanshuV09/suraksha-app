import {
    LineChart,
    Line,
    CartesianGrid,
    XAxis,
    YAxis,
    Tooltip,
    Legend,
} from "recharts";

import type { TimelineGraphPoint, } from "../types/timeline";
import { TimelineChartAdapter } from "../adapters/timelineChartAdapter";

interface TimelineChartProps {
    graph?: TimelineGraphPoint[];
    loading?: boolean;
}

const COLORS = {
    created: "#22c55e",
    modified: "#3b82f6",
    accessed: "#f59e0b",
    deleted: "#ef4444",
    mft_modified: "#a855f7",
};

export default function TimelineChart({
    graph,
    loading = false,
}: TimelineChartProps) {

    if (loading) {
        return (
            <div className="flex h-[520px] items-center justify-center rounded-lg border bg-white">
                Loading timeline...
            </div>
        );
    }

    if (!graph || graph.length === 0) {
        return (
            <div className="flex h-[520px] items-center justify-center rounded-lg border bg-white">
                No timeline available.
            </div>
        );
    }

    const chartData =
        TimelineChartAdapter.adapt(
            graph
        );


    return (
        <div className="overflow-auto rounded-lg border bg-white p-4">

            <LineChart
                width={1100}

                height={480}

                data={chartData}

                margin={{
                    top: 20,
                    right: 30,
                    left: 20,
                    bottom: 20,
                }}

            >

                <CartesianGrid
                    strokeDasharray="3 3"
                />


                <XAxis

                    dataKey="x"

                    tick={{
                        fontSize: 12,
                    }}

                />


                <YAxis

                    domain={[
                        0,
                        "auto",
                    ]}

                />


                <Tooltip />


                <Legend />


                <Line

                    type="monotone"

                    dataKey="created"

                    stroke={COLORS.created}

                    strokeWidth={2}

                    dot={false}

                />


                <Line

                    type="monotone"

                    dataKey="modified"

                    stroke={COLORS.modified}

                    strokeWidth={2}

                    dot={false}

                />


                <Line

                    type="monotone"

                    dataKey="accessed"

                    stroke={COLORS.accessed}

                    strokeWidth={2}

                    dot={false}

                />


                <Line

                    type="monotone"

                    dataKey="deleted"

                    stroke={COLORS.deleted}

                    strokeWidth={2}

                    dot={false}

                />


                <Line

                    type="monotone"

                    dataKey="mft_modified"

                    stroke={COLORS.mft_modified}

                    strokeWidth={2}

                    dot={false}

                />

            </LineChart>

        </div>

    );

}