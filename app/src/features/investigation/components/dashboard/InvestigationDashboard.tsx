import { useMemo } from "react";
import {
    HardDrive,
    Database,
    FolderTree,
    FileText,
    Trash2,
    Image,
} from "lucide-react";

import SummaryCard from "./SummaryCard";

import { useInvestigation } from "../../context/InvestigationContext";
import { formatBytes } from "../../utils/formatBytes";
import type { AnalysisResult } from "../../../analyzer/types/analysis-result";

interface InvestigationDashboardProps {
    analysis: AnalysisResult | null;
}

/**
 * Case summary cards. Counts come from the loaded evidence, so they are
 * the same for a fresh analysis and for a case opened from the Cases page.
 */
export default function InvestigationDashboard({
    analysis,
}: InvestigationDashboardProps) {

    const { evidence } = useInvestigation();

    const counts = useMemo(() => {
        let files = 0;
        let directories = 0;
        let deleted = 0;
        for (const item of evidence) {
            if (item.directory) {
                directories += 1;
            } else {
                files += 1;
                if (item.deleted) {
                    deleted += 1;
                }
            }
        }
        return { records: evidence.length, files, directories, deleted };
    }, [evidence]);

    if (!analysis) {
        return null;
    }

    return (

        <section className="border-b bg-white px-4 py-3">

            <div className="grid grid-cols-6 gap-3">

                <SummaryCard
                    title="Filesystem"
                    value={`${analysis.filesystem || "NTFS"}${analysis.volume_label ? ` · ${analysis.volume_label}` : ""}`}
                    subtitle="Detected filesystem"
                    icon={<HardDrive size={22} />}
                />

                <SummaryCard
                    title="Image Size"
                    value={analysis.image_size ? formatBytes(analysis.image_size) : "—"}
                    subtitle="Evidence image"
                    icon={<Image size={22} />}
                />

                <SummaryCard
                    title="MFT Records"
                    value={counts.records.toLocaleString()}
                    subtitle="Files and folders parsed"
                    icon={<Database size={22} />}
                />

                <SummaryCard
                    title="Files"
                    value={counts.files.toLocaleString()}
                    subtitle="Including deleted"
                    icon={<FileText size={22} />}
                />

                <SummaryCard
                    title="Folders"
                    value={counts.directories.toLocaleString()}
                    subtitle="Directories"
                    icon={<FolderTree size={22} />}
                />

                <SummaryCard
                    title="Deleted Files"
                    value={counts.deleted.toLocaleString()}
                    subtitle="See the Deleted Files tab"
                    icon={<Trash2 size={22} />}
                />

            </div>

        </section>

    );

}
