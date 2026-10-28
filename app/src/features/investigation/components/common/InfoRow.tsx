import type { ReactNode } from "react";

interface InfoRowProps {
    label: string;
    value: ReactNode;
}

export default function InfoRow({
    label,
    value,
}: InfoRowProps) {

    return (

        <div className="grid grid-cols-[180px_1fr] gap-4 border-b border-slate-100 py-2 last:border-b-0">

            <div className="font-medium text-slate-600">
                {label}
            </div>

            <div className="break-all text-slate-900">
                {value}
            </div>

        </div>

    );

}