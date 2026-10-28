import type { PreviewResult } from "../../types/preview";

interface Props {
    preview: PreviewResult;
}

export default function TextViewer({ preview }: Props) {

    return (

        <pre className="h-full overflow-auto p-4 font-mono text-sm">

            {preview.textContent ?? ""}

        </pre>

    );

}