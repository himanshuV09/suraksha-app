import type { PreviewResult } from "../../types/preview";

interface Props {
    preview: PreviewResult;
}

export default function ImageViewer({ preview }: Props) {

    return (

        <div className="flex h-full items-center justify-center overflow-auto bg-slate-100">

            <img
                src={preview.previewUrl}
                alt={preview.filename}
                className="max-h-full max-w-full object-contain"
            />

        </div>

    );

}