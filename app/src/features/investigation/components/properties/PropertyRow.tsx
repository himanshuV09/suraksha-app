interface PropertyRowProps {

    label: string;

    value: string | number;

}

export default function PropertyRow({

    label,

    value,

}: PropertyRowProps) {

    return (

        <div className="flex items-center justify-between border-b border-slate-100 py-2">

            <span className="text-sm text-slate-500">

                {label}

            </span>

            <span className="text-sm font-medium text-slate-800">

                {value}

            </span>

        </div>

    );

}