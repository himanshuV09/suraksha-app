import { useInvestigation } from "../context/InvestigationContext";

export default function StatusBar() {

    const {

        selectedPreview,

    } = useInvestigation();

    return (

        <footer className="flex h-8 items-center justify-between border-t bg-slate-800 px-4 text-xs text-slate-200">

            <div className="flex items-center gap-6">

                <span>

                    Ready

                </span>

                <span>

                    {

                        selectedPreview

                            ? `Selected: ${selectedPreview.evidence.filename}`

                            : "No file selected"

                    }

                </span>

            </div>

            <span>

                Suraksha Forensic Suite

            </span>

        </footer>

    );

}