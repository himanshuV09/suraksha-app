import {
    ChevronRight,
    ChevronDown,
    Folder,
    File,
} from "lucide-react";

import { useState } from "react";

import type {
    FilesystemNode,
} from "../../types/filesystem";

import {
    useInvestigation,
} from "../../context/InvestigationContext";

interface TreeNodeProps {

    node: FilesystemNode;

}

export default function TreeNode({

    node,

}: TreeNodeProps) {

    const [expanded, setExpanded] =
        useState(false);

    const { selectedPreview, setSelectedPreview, } = useInvestigation();

    const children =
        Object.values(node.children);

    const hasChildren =
        children.length > 0;

    const isSelected =
        selectedPreview?.evidence.record_number ===
            node.evidence?.record_number &&
        (
            selectedPreview?.artifact?.path ?? null
        ) === (
            node.artifact?.path ?? null
        );

    return (

        <div>

            <button

                onClick={() => {
                    if (hasChildren) {
                        setExpanded(!expanded);
                    }

                    if (
                        node.evidence &&
                        (
                            !node.directory ||
                            node.artifact
                        )
                    ) {
                        setSelectedPreview({
                            evidence: node.evidence,
                            artifact: node.artifact ?? undefined,
                        });
                    }
                }}

                className={`flex w-full items-center gap-2 rounded px-2 py-1 text-left hover:bg-slate-100
                    ${
                        isSelected
                            ? "bg-indigo-50"
                            : ""
                    }
                `}

            >

                {

                    hasChildren

                        ? expanded

                            ? <ChevronDown size={14}/>

                            : <ChevronRight size={14}/>

                        : <div className="w-[14px]" />

                }

                {

                    node.directory

                        ? <Folder size={16}/>

                        : <File size={16}/>

                }

                <span>

                    {node.name}

                </span>

            </button>

            {

                expanded &&

                hasChildren && (

                    <div className="ml-4 border-l border-slate-200 pl-3">

                        {

                            children.map(child => (

                                <TreeNode

                                    key={child.name}

                                    node={child}

                                />

                            ))

                        }

                    </div>

                )

            }

        </div>

    );

}