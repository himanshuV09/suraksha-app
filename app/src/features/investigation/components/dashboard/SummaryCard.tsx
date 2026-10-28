import type { ReactNode } from "react";

interface SummaryCardProps {

    title: string;

    value: string | number;

    icon: ReactNode;

    subtitle?: string;

}

export default function SummaryCard({

    title,

    value,

    icon,

    subtitle,

}: SummaryCardProps) {

    return (

        <div className="flex items-center justify-between rounded-lg border bg-white px-4 py-3 shadow-sm">

            <div className="min-w-0">

                <p className="text-xs font-medium uppercase tracking-wide text-slate-500">

                    {title}

                </p>

                <h3 className="mt-1 text-lg font-semibold text-slate-800">

                    {value}

                </h3>

                {

                    subtitle && (

                        <p className="truncate text-xs text-slate-400">

                            {subtitle}

                        </p>

                    )

                }

            </div>

            <div className="ml-3 rounded-md bg-indigo-50 p-2 text-indigo-600">

                {icon}

            </div>

        </div>

    );

}