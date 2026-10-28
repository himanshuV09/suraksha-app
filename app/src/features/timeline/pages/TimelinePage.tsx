import { useInvestigation } from "@/features/investigation/context/InvestigationContext";
import InvestigationLayout from "@/features/investigation/layout/InvestigationLayout";

import TimelineToolbar from "../components/toolbar/TimelineToolbar";
import TimelineSummaryCards from "../components/cards/TimelineSummaryCards";
import TimelineChart from "../components/TimelineChart";
import TimelineDetails from "../components/details/TimelineDetails";

import { useTimeline } from "../hooks/useTimeline";

export default function TimelinePage() {

    const {
        databasePath,
        caseId,
        selectedEvidence,
    } = useInvestigation();



    const {
        data,
        isLoading,
        error,
    } = useTimeline({
        databasePath,
        caseId,
        interval: "day",
        recordNumber: selectedEvidence?.record_number,
    });


    if (!databasePath || caseId === null) {
        return (
            <div className="flex h-full items-center justify-center text-slate-500">
                No investigation loaded.
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex h-full items-center justify-center text-red-500">
                Failed to load timeline.
            </div>
        );
    }

    return (

        <InvestigationLayout>

            <div className="flex h-full flex-col gap-4 overflow-auto p-4">

                <TimelineToolbar />

                <TimelineSummaryCards
                    summary={data?.summary}
                />

                <div className="rounded-lg border bg-white p-4">

                    <TimelineChart
                        graph={data?.graph}
                        loading={isLoading}
                    />

                </div>

                <TimelineDetails
                    events={data?.events ?? []}
                />

            </div>

        </InvestigationLayout>

    );

}