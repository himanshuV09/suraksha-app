import { PanelResizeHandle } from "react-resizable-panels";

export default function ResizeHandle() {

    return (

        <PanelResizeHandle
            className="
                group
                relative
                flex
                w-2
                items-center
                justify-center
                transition-colors
            "
        >

            {/* Invisible larger drag area */}

            <div
                className="
                    absolute
                    inset-y-0
                    w-px
                    bg-slate-300
                    group-hover:bg-indigo-500
                    transition-colors
                "
            />

            {/* Grip */}

            <div
                className="
                    z-10
                    h-12
                    w-1
                    rounded-full
                    bg-slate-400
                    group-hover:bg-indigo-600
                    transition-colors
                "
            />

        </PanelResizeHandle>

    );

}