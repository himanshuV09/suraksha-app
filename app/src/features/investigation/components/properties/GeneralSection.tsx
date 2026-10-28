import PropertyRow from "./PropertyRow";

import type { EvidenceRecord } from "../../types/evidence";

interface GeneralSectionProps {

    record: EvidenceRecord;

}

export default function GeneralSection({

    record,

}: GeneralSectionProps) {

    return (

        <div className="rounded-lg border bg-white p-4">

            <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-600">

                General

            </h3>

            <PropertyRow
                label="Filename"
                value={record.filename}
            />

            <PropertyRow
                label="Record Number"
                value={record.record_number}
            />

            <PropertyRow
                label="Full Path"
                value={record.full_path ?? "-"}
            />

            <PropertyRow
                label="Parent Record"
                value={record.parent_record ?? "-"}
            />

            <PropertyRow
                label="Record Type"
                value={record.record_type}
            />

        </div>

    );

}