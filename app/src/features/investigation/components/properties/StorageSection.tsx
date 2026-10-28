import PropertyRow from "./PropertyRow";

import type { EvidenceRecord } from "../../types/evidence";

interface StorageSectionProps {

    record: EvidenceRecord;

}

export default function StorageSection({

    record,

}: StorageSectionProps) {

    return (

        <div className="rounded-lg border bg-white p-4">

            <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-600">

                Storage

            </h3>

            <PropertyRow
                label="File Size"
                value={`${record.file_size} Bytes`}
            />

            <PropertyRow
                label="Allocated Size"
                value={`${record.allocated_size} Bytes`}
            />

            <PropertyRow
                label="Fragment Count"
                value={record.fragment_count}
            />

            <PropertyRow
                label="Slack Space"
                value={`${record.slack_space} Bytes`}
            />

        </div>

    );

}