import { EmptyState } from "../components/common";
import { usePreview } from "../hooks/usePreview";

import PreviewToolbar from "./PreviewToolbar";
import PreviewRenderer from "./PreviewRenderer";

export default function PreviewTab() {

    const { selectedPreview, selectedRecovered, preview, loading, error } = usePreview();

    if (!selectedPreview && !selectedRecovered) {
        return <EmptyState message="Select a file to preview." />;
    }

    if (loading) {
        return <EmptyState message="Loading preview..." />;
    }

    if (error) {
        return <EmptyState message={error} />;
    }

    if (!preview) {
        return <EmptyState message="Preview unavailable." />;
    }

    return (

        <div className="flex h-full w-full flex-col">

            <PreviewToolbar />

            {selectedRecovered && (
                <div
                    className={`border-b px-3 py-1.5 text-xs ${
                        preview.hash_verified
                            ? "bg-emerald-50 text-emerald-800"
                            : "bg-red-50 text-red-700"
                    }`}
                >
                    Carved from free space at offset {selectedRecovered.source_offset.toLocaleString()} ·{" "}
                    {preview.hash_verified
                        ? "SHA-256 matches the value recorded at recovery"
                        : "SHA-256 does NOT match the value recorded at recovery"}
                </div>
            )}

            <div className="flex flex-1 items-center justify-center overflow-auto">

                <PreviewRenderer
                    preview={preview}
                />

            </div>

        </div>

    );

}
