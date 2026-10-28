import type { ReactNode } from "react";
import { Briefcase, Clock3, FolderOpen, ScanSearch } from "lucide-react";

import type { AppPage } from "../../types/navigation";

interface SidebarProps {
    currentPage: AppPage;
    onNavigate: (page: AppPage) => void;
    /** Evidence Explorer and Timeline need an open case. */
    caseOpen: boolean;
    caseName?: string;
}

interface Item {
    page: AppPage;
    label: string;
    icon: ReactNode;
    needsCase?: boolean;
}

const ITEMS: Item[] = [
    { page: "cases", label: "Cases", icon: <Briefcase size={18} /> },
    { page: "analyzer", label: "New Analysis", icon: <ScanSearch size={18} /> },
    { page: "investigation", label: "Evidence Explorer", icon: <FolderOpen size={18} />, needsCase: true },
    { page: "timeline", label: "Timeline", icon: <Clock3 size={18} />, needsCase: true },
];

export default function Sidebar({ currentPage, onNavigate, caseOpen, caseName }: SidebarProps) {
    return (
        <aside className="flex h-screen w-64 shrink-0 flex-col border-r border-slate-200 bg-white px-4 py-6">
            <div className="mb-8 px-2">
                <h1 className="text-2xl font-bold tracking-wide text-indigo-600">SURAKSHA</h1>
                <p className="text-xs text-slate-500">Digital Forensic Suite</p>
            </div>

            <nav className="flex flex-col gap-1" aria-label="Main">
                {ITEMS.map((item) => {
                    const disabled = item.needsCase && !caseOpen;
                    return (
                        <button
                            key={item.page}
                            type="button"
                            onClick={() => onNavigate(item.page)}
                            disabled={disabled}
                            title={disabled ? "Open or analyze a case first" : undefined}
                            aria-current={currentPage === item.page ? "page" : undefined}
                            className={`sidebar-item ${currentPage === item.page ? "sidebar-active" : ""} disabled:cursor-not-allowed disabled:opacity-40`}
                        >
                            {item.icon}
                            {item.label}
                        </button>
                    );
                })}
            </nav>

            {caseOpen && caseName && (
                <div className="mt-6 rounded-md bg-slate-50 px-3 py-2 text-xs">
                    <div className="text-slate-500">Open case</div>
                    <div className="truncate font-medium text-slate-800" title={caseName}>{caseName}</div>
                </div>
            )}

            <div className="mt-auto px-2 text-xs text-slate-400">
                Read-only analysis · evidence images are never modified
            </div>
        </aside>
    );
}
