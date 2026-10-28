import { Badge, InfoRow, Section } from "../../common";
import { formatBytes } from "../../../utils";
import type { EvidenceRecord } from "../../../types/evidence";

interface RecoverySectionProps {
    evidence: EvidenceRecord;
}

export default function RecoverySection({
    evidence,
}: RecoverySectionProps) {
    return (
        <Section title="Recovery">

            <InfoRow
                label="Deleted"
                value={
                    evidence.deleted ? (
                        <Badge color="red">Deleted</Badge>
                    ) : (
                        <Badge color="green">Active</Badge>
                    )
                }
            />

            <InfoRow
                label="Directory"
                value={
                    evidence.directory ? (
                        <Badge color="blue">Directory</Badge>
                    ) : (
                        <Badge color="gray">File</Badge>
                    )
                }
            />

            <InfoRow
                label="Fragmented"
                value={
                    evidence.fragmented ? (
                        <Badge color="yellow">Yes</Badge>
                    ) : (
                        <Badge color="green">No</Badge>
                    )
                }
            />

            <InfoRow
                label="Fragment Count"
                value={evidence.fragment_count ?? 0}
            />

            <InfoRow
                label="Slack Space"
                value={formatBytes(evidence.slack_space ?? 0)}
            />

            <InfoRow
                label="Slack Entropy"
                value={
                    evidence.slack_entropy !== undefined
                        ? evidence.slack_entropy.toFixed(2)
                        : "N/A"
                }
            />

        </Section>
    );
}