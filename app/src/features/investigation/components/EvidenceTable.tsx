import type { EvidenceRecord } from "../types/evidence";

import { useInvestigation } from "../context/InvestigationContext";

import { useEvidence } from "../hooks/useEvidence";


interface EvidenceTableProps {

    evidence: EvidenceRecord[];

    loading: boolean;

}


export default function EvidenceTable({

    evidence,

    loading,

}: EvidenceTableProps) {


    const {

        selectedEvidence,

    } = useInvestigation();


    const {

        selectRecord,

    } = useEvidence();


    return (

        <main
            className="
                flex
                h-full
                flex-col
                rounded-lg
                border
                bg-white
                shadow-sm
            "
        >

            {/* Header */}

            <div
                className="
                    border-b
                    px-4
                    py-3
                "
            >

                <h2
                    className="
                        font-semibold
                        text-slate-800
                    "
                >
                    Evidence
                </h2>

            </div>


            {/* Table */}

            <div
                className="
                    flex-1
                    overflow-auto
                "
            >

                <table
                    className="
                        w-full
                        table-fixed
                        border-collapse
                        text-sm
                    "
                >

                    <thead
                        className="
                            sticky
                            top-0
                            bg-slate-50
                        "
                    >

                        <tr
                            className="
                                border-b
                                text-xs
                                uppercase
                                tracking-wide
                                text-slate-500
                            "
                        >

                            <th
                                className="
                                    w-20
                                    p-2
                                    text-left
                                "
                            >
                                Record
                            </th>


                            <th
                                className="
                                    p-2
                                    text-left
                                "
                            >
                                Filename
                            </th>


                            <th
                                className="
                                    w-28
                                    p-2
                                    text-right
                                "
                            >
                                Size
                            </th>


                            <th
                                className="
                                    w-24
                                    p-2
                                    text-center
                                "
                            >
                                Deleted
                            </th>


                            <th
                                className="
                                    w-20
                                    p-2
                                    text-center
                                "
                            >
                                Risk
                            </th>

                        </tr>

                    </thead>


                    <tbody>

                        {/* Loading */}

                        {loading && (

                            <tr>

                                <td
                                    colSpan={5}
                                    className="
                                        p-4
                                        text-center
                                        text-slate-500
                                    "
                                >
                                    Loading evidence...
                                </td>

                            </tr>

                        )}


                        {/* Evidence */}

                        {!loading &&
                            evidence.map((record) => (

                                <tr
                                    key={
                                        record.record_number
                                    }

                                    onClick={() => {


                                        selectRecord(
                                            record
                                        );

                                    }}

                                    className={`
                                        cursor-pointer
                                        border-b
                                        transition-colors
                                        hover:bg-slate-100

                                        ${
                                            selectedEvidence
                                                ?.record_number ===
                                            record.record_number

                                                ? "bg-indigo-100"

                                                : ""
                                        }
                                    `}
                                >

                                    {/* Record */}

                                    <td className="p-2">

                                        {record.record_number}

                                    </td>


                                    {/* Filename */}

                                    <td
                                        className="
                                            truncate
                                            p-2
                                            font-medium
                                            text-slate-800
                                        "

                                        title={
                                            record.full_path ?? ""
                                        }
                                    >

                                        {record.filename}

                                    </td>


                                    {/* Size */}

                                    <td
                                        className="
                                            p-2
                                            text-right
                                            text-slate-600
                                        "
                                    >

                                        {record.file_size}

                                    </td>


                                    {/* Deleted */}

                                    <td
                                        className="
                                            p-2
                                            text-center
                                        "
                                    >

                                        {record.deleted
                                            ? "Yes"
                                            : "No"}

                                    </td>


                                    {/* Risk */}

                                    <td
                                        className="
                                            p-2
                                            text-center
                                        "
                                    >

                                        {record.risk_score}

                                    </td>

                                </tr>

                            ))}


                        {/* Empty */}

                        {!loading &&
                            evidence.length === 0 && (

                                <tr>

                                    <td
                                        colSpan={5}
                                        className="
                                            p-8
                                            text-center
                                            text-slate-500
                                        "
                                    >
                                        No evidence found.
                                    </td>

                                </tr>

                            )}

                    </tbody>

                </table>

            </div>

        </main>

    );

}