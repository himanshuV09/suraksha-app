import { Badge, InfoRow, Section } from "../../common";
import { formatRisk } from "../../../utils";
import type { EvidenceRecord } from "../../../types/evidence";

interface AnalysisSectionProps {
    evidence: EvidenceRecord;
}

export default function AnalysisSection({
    evidence,
}: AnalysisSectionProps) {

    const riskLevel = formatRisk(evidence.risk_score);

    const badgeColor =
        riskLevel === "High"
            ? "red"
            : riskLevel === "Medium"
            ? "yellow"
            : "green";

    return (
        <Section title="Analysis">

            <InfoRow
                label="Risk Score"
                value={evidence.risk_score}
            />

            <InfoRow
                label="Risk Level"
                value={
                    <Badge color={badgeColor}>
                        {riskLevel}
                    </Badge>
                }
            />

        </Section>
    );
}