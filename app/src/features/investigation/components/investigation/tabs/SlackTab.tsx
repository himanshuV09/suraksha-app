import { useEffect, useState } from "react";

import { errorMessage } from "../../../../../lib/engine";
import { useInvestigation } from "../../../context/InvestigationContext";
import { investigationService } from "../../../services/investigation.service";
import { formatBytes } from "../../../utils/formatBytes";

type Slack = Awaited<ReturnType<typeof investigationService.loadFileSlack>>;

const BYTES_PER_ROW = 16;
const MAX_ROWS = 256; // 4 KiB shown; the rest is summarized

function hexRows(hex: string, baseOffset: number) {
    const bytes: number[] = [];
    for (let i = 0; i < hex.length && bytes.length < BYTES_PER_ROW * MAX_ROWS; i += 2) {
        bytes.push(Number.parseInt(hex.slice(i, i + 2), 16));
    }
    const rows = [];
    for (let i = 0; i < bytes.length; i += BYTES_PER_ROW) {
        const chunk = bytes.slice(i, i + BYTES_PER_ROW);
        rows.push({
            offset: baseOffset + i,
            hex: chunk.map((b) => b.toString(16).padStart(2, "0")).join(" "),
            text: chunk.map((b) => (b >= 0x20 && b < 0x7f ? String.fromCharCode(b) : ".")).join(""),
        });
    }
    return rows;
}

/** Slack space of the selected file: data left over from earlier files. */
export default function SlackTab() {
    const { databasePath, selectedEvidence } = useInvestigation();
    const [slack, setSlack] = useState<Slack | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!selectedEvidence || !databasePath) {
            setSlack(null);
            return;
        }
        let cancelled = false;
        setLoading(true);
        setError(null);
        investigationService
            .loadFileSlack(databasePath, selectedEvidence.evidence_id)
            .then((result) => !cancelled && setSlack(result))
            .catch((err) => !cancelled && setError(errorMessage(err)))
            .finally(() => !cancelled && setLoading(false));
        return () => {
            cancelled = true;
        };
    }, [databasePath, selectedEvidence]);

    if (!selectedEvidence) {
        return <p className="p-4 text-sm text-slate-500">Select a file in the evidence table.</p>;
    }
    if (loading) {
        return <p className="p-4 text-sm text-slate-500">Reading slack space…</p>;
    }
    if (error) {
        return <p role="alert" className="p-4 text-sm text-red-700">{error}</p>;
    }
    if (!slack) {
        return null;
    }
    if (slack.resident || slack.slack_size === 0) {
        return (
            <p className="p-4 text-sm text-slate-500">
                {slack.resident
                    ? "This file is stored inside its MFT record, so it has no cluster slack."
                    : "This file ends exactly at a cluster boundary: no slack."}
            </p>
        );
    }

    const rows = hexRows(slack.data, slack.slack_offset ?? 0);

    return (
        <div className="flex h-full min-h-0 flex-col bg-white text-slate-800">
            <div className="border-b p-3 text-sm">
                <span className="font-semibold">{slack.filename}</span>: {formatBytes(slack.slack_size)} of slack
                after byte {slack.slack_offset?.toLocaleString()}
                {slack.all_zero && <span className="ml-2 text-slate-500">(all zero: nothing left over)</span>}
                {slack.truncated && <span className="ml-2 text-amber-700">(first 64 KiB shown)</span>}
            </div>

            {slack.strings.length > 0 && (
                <div className="max-h-32 overflow-auto border-b bg-amber-50 p-3 text-xs">
                    <p className="mb-1 font-semibold text-amber-900">Readable text in slack</p>
                    {slack.strings.map((text, index) => (
                        <p key={index} className="font-mono">{text}</p>
                    ))}
                </div>
            )}

            <div className="min-h-0 flex-1 overflow-auto p-3 font-mono text-xs">
                {rows.map((row) => (
                    <div key={row.offset} className="flex gap-4 whitespace-pre">
                        <span className="text-slate-400">{row.offset.toString(16).padStart(8, "0")}</span>
                        <span>{row.hex.padEnd(BYTES_PER_ROW * 3 - 1)}</span>
                        <span className="text-slate-600">{row.text}</span>
                    </div>
                ))}
            </div>
        </div>
    );
}
