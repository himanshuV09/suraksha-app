import type { TimelineEvent } from "../../types/timeline";

interface TimelineDetailsProps {
    events: TimelineEvent[];
}

export default function TimelineDetails({
    events,
}: TimelineDetailsProps) {

    return (

        <div className="rounded-lg border border-slate-200 bg-white shadow-sm">

            {/* Header */}

            <div className="border-b px-5 py-3">

                <h3 className="text-lg font-semibold text-slate-800">
                    Timeline Events
                </h3>

                <p className="text-sm text-slate-500">
                    Individual forensic events associated with the investigation.
                </p>

            </div>


            {/* Event Table */}

            <div className="max-h-[450px] overflow-auto">

                <table className="min-w-full border-collapse text-sm">

                    <thead className="sticky top-0 z-10 bg-slate-100">

                        <tr className="border-b text-left text-xs uppercase tracking-wide text-slate-500">

                            <th className="whitespace-nowrap px-4 py-3">
                                Timestamp
                            </th>

                            <th className="whitespace-nowrap px-4 py-3">
                                Event
                            </th>

                            <th className="whitespace-nowrap px-4 py-3">
                                Record
                            </th>

                            <th className="px-4 py-3">
                                Filename
                            </th>

                            <th className="px-4 py-3">
                                Source
                            </th>

                            <th className="px-4 py-3">
                                Deleted
                            </th>

                        </tr>

                    </thead>


                    <tbody>

                        {events.length === 0 && (

                            <tr>

                                <td
                                    colSpan={6}
                                    className="px-4 py-8 text-center text-slate-500"
                                >
                                    No timeline events available.
                                </td>

                            </tr>

                        )}


                        {events.map((event, index) => (

                            <tr
                                key={`${event.record_number}-${event.timestamp}-${event.event_type}-${index}`}
                                className="border-b transition-colors hover:bg-slate-50"
                            >

                                {/* Timestamp */}

                                <td className="whitespace-nowrap px-4 py-3 font-mono text-xs text-slate-700">

                                    {event.timestamp
                                        ? new Date(
                                            event.timestamp
                                        ).toLocaleString()
                                        : "Unknown"}

                                </td>


                                {/* Event Type */}

                                <td className="px-4 py-3">

                                    <span
                                        className={`
                                            inline-flex
                                            rounded-full
                                            px-2.5
                                            py-1
                                            text-xs
                                            font-medium

                                            ${
                                                event.event_type === "Created"
                                                    ? "bg-green-100 text-green-700"

                                                : event.event_type === "Modified"
                                                    ? "bg-blue-100 text-blue-700"

                                                : event.event_type === "Accessed"
                                                    ? "bg-amber-100 text-amber-700"

                                                : event.event_type === "Deleted"
                                                    ? "bg-red-100 text-red-700"

                                                : "bg-purple-100 text-purple-700"
                                            }
                                        `}
                                    >

                                        {event.event_type}

                                    </span>

                                </td>


                                {/* Record Number */}

                                <td className="px-4 py-3 font-mono text-xs text-slate-600">

                                    {event.record_number}

                                </td>


                                {/* Filename */}

                                <td
                                    className="max-w-[260px] truncate px-4 py-3 font-medium text-slate-800"
                                    title={event.full_path}
                                >

                                    {event.filename}

                                </td>


                                {/* Source */}

                                <td className="px-4 py-3 text-slate-600">

                                    {event.source}

                                </td>


                                {/* Deleted */}

                                <td className="px-4 py-3">

                                    <span
                                        className={
                                            event.deleted
                                                ? "font-medium text-red-600"
                                                : "text-slate-500"
                                        }
                                    >

                                        {event.deleted
                                            ? "Yes"
                                            : "No"}

                                    </span>

                                </td>

                            </tr>

                        ))}

                    </tbody>

                </table>

            </div>

        </div>

    );
}