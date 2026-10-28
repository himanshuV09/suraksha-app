import type { PreviewResult } from "../types/preview";

import UnsupportedViewer from "./UnsupportedViewer";

import ImageViewer from "./viewers/ImageViewer";
import TextViewer from "./viewers/TextViewer";
import PdfViewer from "./viewers/PdfViewer";
import HtmlViewer from "./viewers/HtmlViewer";
import AudioViewer from "./viewers/AudioViewer";
import VideoViewer from "./viewers/VideoViewer";
import BinaryViewer from "./viewers/BinaryViewer";
import DocxViewer from "./viewers/DocxViewer";
import PptxViewer from "./viewers/PptxViewer";

interface PreviewRendererProps {
    preview: PreviewResult;
}

export default function PreviewRenderer({
    preview,
}: PreviewRendererProps) {


    switch (preview.type) {

        case "image":
            return <ImageViewer preview={preview}/>;

        case "text":
            return <TextViewer preview={preview}/>;

        case "pdf":
            return <PdfViewer />;

        case "html":
            return <HtmlViewer />;

        case "audio":
            return <AudioViewer />;

        case "video":
            return <VideoViewer />;

        case "binary":
            return <BinaryViewer />;

        case "docx":
            return <DocxViewer preview={preview} />;

        case "pptx":
            return <PptxViewer preview={preview} />;

        default:
            return <UnsupportedViewer />;

    }

}