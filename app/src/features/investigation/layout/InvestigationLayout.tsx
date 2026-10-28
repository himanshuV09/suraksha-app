import Toolbar from "../components/Toolbar";
import StatusBar from "../components/StatusBar";
import InvestigationDashboard from "../components/dashboard/InvestigationDashboard";

import type { ReactNode } from "react";

import { useInvestigation } from "../context/InvestigationContext";

export default function InvestigationLayout({

    children,

}: {

    children: ReactNode;

}) {

    const {

        analysis,

    } = useInvestigation();

    return (

        <div className="flex h-full flex-col bg-slate-100">

            <Toolbar />

            <InvestigationDashboard
                analysis={analysis}
            />

            <div className="flex-1 overflow-hidden">

                {children}

            </div>

            <StatusBar />

        </div>

    );

}