export type PreviewType =
    | "image"
    | "text"
    | "pdf"
    | "html"
    | "audio"
    | "video"
    | "binary"
    | "docx"
    | "pptx"
    | "unsupported";

export interface PreviewMetadata {
    width?: number;
    height?: number;

    pages?: number;

    duration?: number;

    encoding?: string;

    lineCount?: number;
}

export interface BinaryInfo {
    magicNumber?: string;
    signature?: string;
}

export interface OfficeMetadata {

    author?: string;

    title?: string;

    subject?: string;

    created?: string;

    modified?: string;

    last_modified_by?: string;

}

export interface OfficeImage {

    name: string;

    mime: string;

    size: number;

    previewUrl: string;

}

export interface Slide {

    slide: number;

    text: string;

}

export interface PreviewResult {

    type: PreviewType;

    mime: string;

    filename: string;

    size: number;

    previewUrl?: string;

    textContent?: string;

    metadata?: PreviewMetadata | OfficeMetadata;

    binaryInfo?: BinaryInfo;

    // DOCX

    text?: string;

    tables?: string[][][];

    // PPTX

    slides?: Slide[];

    // Shared Office

    images?: OfficeImage[];

}