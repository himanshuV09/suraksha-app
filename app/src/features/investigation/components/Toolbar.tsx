import { Briefcase } from "lucide-react";

import { useInvestigation } from "../context/InvestigationContext";

/** Which case and evidence image is open. */
export default function Toolbar() {
    const { analysis } = useInvestigation();

    if (!analysis) {
        return null;
    }

    return (
        <header className="flex flex-wrap items-center gap-x-6 gap-y-1 border-b bg-white px-4 py-2 text-sm">
            <span className="flex items-center gap-2 font-semibold text-slate-900">
                <Briefcase size={16} className="text-indigo-600" />
                {analysis.case_name || `Case #${analysis.case_id}`}
            </span>
            {analysis.investigator && (
                <span className="text-slate-500">Investigator: {analysis.investigator}</span>
            )}
            <span className="min-w-0 truncate font-mono text-xs text-slate-500" title={analysis.image_path}>
                {analysis.image_path}
            </span>
        </header>
    );
}
