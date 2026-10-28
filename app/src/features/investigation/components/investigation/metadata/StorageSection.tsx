import { InfoRow, Section } from "../../common";
import { formatBytes } from "../../../utils";
import type { EvidenceRecord } from "../../../types/evidence";

interface StorageSectionProps {
    evidence: EvidenceRecord;
}

export default function StorageSection({
    evidence,
}: StorageSectionProps) {
    return (
        <Section title="Storage">
            <InfoRow
                label="Record Number"
                value={evidence.record_number}
            />

            <InfoRow
                label="Parent Record"
                value={evidence.parent_record ?? "-"}
            />

            <InfoRow
                label="File Size"
                value={formatBytes(evidence.file_size)}
            />

            <InfoRow
                label="Allocated Size"
                value={formatBytes(evidence.allocated_size)}
            />
        </Section>
    );
}