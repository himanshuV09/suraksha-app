import { useInvestigation } from "../../../context/InvestigationContext";

import { Card, EmptyState } from "../../common";

import GeneralSection from "../metadata/GeneralSection";
import StorageSection from "../metadata/StorageSection";
import RecoverySection from "../metadata/RecoverySection";
import AnalysisSection from "../metadata/AnalysisSection";

export default function MetadataTab() {

    const { selectedPreview } = useInvestigation();

    if (!selectedPreview) {
        return (
            <EmptyState message="Select a file to view metadata." />
        );
    }

    const evidence = selectedPreview.evidence;

    return (

        <Card className="overflow-hidden">

            <GeneralSection
                evidence={evidence}
            />

            <StorageSection
                evidence={evidence}
            />

            <RecoverySection
                evidence={evidence}
            />

            <AnalysisSection
                evidence={evidence}
            />

        </Card>

    );

}