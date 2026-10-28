
import type { EvidenceRecord } from "./evidence";
import type { ContainerArtifact } from "./container-artifact";

export type FilesystemNodeType =
    | "image"
    | "volume"
    | "directory"
    | "file"
    | "metadata"
    | "orphan"
    | "unallocated";

export interface FilesystemNode {
    name: string;

    directory: boolean;

    evidence: EvidenceRecord | null;

    artifact: ContainerArtifact | null;

    children: Record<string, FilesystemNode>;

    // Optional fields for the forensic evidence tree.
    nodeType?: FilesystemNodeType;
    filesystem?: string;
    startOffset?: number;
    size?: number;
    deleted?: boolean;
}

export interface FilesystemResponse {
    success: boolean;

    case_id: number;

    tree: FilesystemNode;
}
