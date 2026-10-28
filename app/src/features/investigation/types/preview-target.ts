import type { EvidenceRecord } from "./evidence";
import type { ContainerArtifact } from "./container-artifact";

export interface PreviewTarget {

    evidence: EvidenceRecord;

    artifact?: ContainerArtifact;

}