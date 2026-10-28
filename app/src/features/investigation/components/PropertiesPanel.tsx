import { useInvestigation, } from "../context/InvestigationContext";

import GeneralSection from "./properties/GeneralSection";
import StorageSection from "./properties/StorageSection";
import StatusSection from "./properties/StatusSection";


export default function PropertiesPanel(){

    const {

        selectedEvidence,

    } = useInvestigation();

    if (!selectedEvidence) {

        return (

            <section className="flex h-full flex-col rounded-lg border bg-white shadow-sm">

                <div className="border-b px-4 py-3">

                    <h2 className="font-semibold text-slate-800">

                        Properties

                    </h2>

                </div>

                <div className="flex flex-1 items-center justify-center p-6">

                    <div className="rounded-lg border border-dashed border-slate-300 p-8 text-center">

                        <p className="text-sm text-slate-500">

                            Select an evidence item to view metadata.

                        </p>

                    </div>
                
                </div>

            </section>

        );

    }

    return (

        <section className="flex h-full flex-col rounded-lg border bg-white shadow-sm">

            <div className="border-b px-4 py-3">

                <h2 className="font-semibold text-slate-800">

                    Properties

                </h2>

            </div>

            <div className="flex-1 overflow-auto p-4 space-y-4">

                <GeneralSection
                    record={selectedEvidence}
                />

                <StorageSection
                    record={selectedEvidence}
                />

                <StatusSection
                    record={selectedEvidence}
                />

            </div>

        </section>

    );

}