import { useState } from "react";

type TimelineInterval = "day" | "week" | "month" | "year";

interface TimelineToolbarProps {
    interval?: TimelineInterval;
    onIntervalChange?: (interval: TimelineInterval) => void;
    onRefresh?: () => void;
    onExport?: () => void;
    onSearch?: (value: string) => void;
}

const intervals: TimelineInterval[] = [
    "day",
    "week",
    "month",
    "year",
];

export default function TimelineToolbar({
    interval = "day",
    onIntervalChange,
    onRefresh,
    onExport,
    onSearch,
}: TimelineToolbarProps) {
    const [search, setSearch] = useState("");

    return (
        <div className="flex flex-wrap items-center justify-between gap-4 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">

            {/* Left */}
            <div className="flex items-center gap-3">

                <h2 className="text-lg font-semibold text-slate-800">
                    Timeline
                </h2>

                <div className="flex overflow-hidden rounded-md border">

                    {intervals.map((item) => (
                        <button
                            key={item}
                            onClick={() => onIntervalChange?.(item)}
                            className={`px-4 py-2 text-sm font-medium capitalize transition-colors ${
                                interval === item
                                    ? "bg-indigo-600 text-white"
                                    : "bg-white text-slate-600 hover:bg-slate-100"
                            }`}
                        >
                            {item}
                        </button>
                    ))}

                </div>

            </div>

            {/* Center */}
            <div className="flex-1 min-w-[220px]">

                <input
                    type="text"
                    value={search}
                    placeholder="Search timeline..."
                    onChange={(e) => {
                        setSearch(e.target.value);
                        onSearch?.(e.target.value);
                    }}
                    className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm outline-none transition focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200"
                />

            </div>

            {/* Right */}
            <div className="flex items-center gap-2">

                <button
                    onClick={onRefresh}
                    className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-100"
                >
                    Refresh
                </button>

                <button
                    onClick={onExport}
                    className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-700"
                >
                    Export
                </button>

            </div>

        </div>
    );
}