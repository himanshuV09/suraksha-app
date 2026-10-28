import SummaryCard from "./SummaryCard";
import type { TimelineSummary } from "../../types/timeline";

interface TimelineSummaryCardsProps {
    summary?: TimelineSummary;
}

export default function TimelineSummaryCards({
    summary,
}: TimelineSummaryCardsProps) {

    if (!summary) {
        return null;
    }

    return (

        <div className="grid grid-cols-5 gap-4">

            <SummaryCard
                title="Total Events"
                value={summary.total_events}
            />

            <SummaryCard
                title="Created"
                value={summary.created}
            />

            <SummaryCard
                title="Modified"
                value={summary.modified}
            />

            <SummaryCard
                title="Deleted"
                value={summary.deleted}
            />

            <SummaryCard
                title="Accessed"
                value={summary.accessed}
            />

        </div>

    );

}