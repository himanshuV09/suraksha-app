import PropertyRow from "./PropertyRow";

import type { EvidenceRecord } from "../../types/evidence";

interface StatusSectionProps {

    record: EvidenceRecord;

}

export default function StatusSection({

    record,

}: StatusSectionProps) {

    return (

        <div className="rounded-lg border bg-white p-4">

            <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-600">

                Status

            </h3>

            <PropertyRow
                label="Deleted"
                value={record.deleted ? "Yes" : "No"}
            />

            <PropertyRow
                label="Directory"
                value={record.directory ? "Yes" : "No"}
            />

            <PropertyRow
                label="Risk Score"
                value={record.risk_score}
            />

        </div>

    );

}