export interface ContainerArtifact {

    artifact_id: number;

    parent_record: number;

    path: string;

    name: string;

    directory: boolean;

    size: number;

    mime_type: string | null;

}