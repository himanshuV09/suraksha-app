import type { ReactNode } from "react";

interface SectionProps {
    title: string;
    children: ReactNode;
}

export default function Section({
    title,
    children,
}: SectionProps) {
    return (
        <section className="border-b last:border-b-0">
            <div className="bg-slate-50 px-4 py-2 text-sm font-semibold text-slate-700">
                {title}
            </div>

            <div className="space-y-2 p-4">
                {children}
            </div>
        </section>
    );
}