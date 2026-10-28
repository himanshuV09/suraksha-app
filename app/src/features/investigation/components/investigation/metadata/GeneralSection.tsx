import { InfoRow, Section } from "../../common/";
import type { EvidenceRecord } from "../../../types/evidence";

interface GeneralSectionProps {
    evidence: EvidenceRecord;
}

export default function GeneralSection({
    evidence,
}: GeneralSectionProps) {
    return (
        <Section title="General">
            <InfoRow
                label="Filename"
                value={evidence.filename}
            />

            <InfoRow
                label="Full Path"
                value={evidence.full_path ?? "-"}
            />

            <InfoRow
                label="Record Type"
                value={evidence.record_type}
            />
        </Section>
    );
}