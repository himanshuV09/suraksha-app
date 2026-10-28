import type { PreviewResult } from "../../types/preview";

interface Props {
    preview: PreviewResult;
}

export default function DocxViewer({ preview }: Props) {

    return (

        <div className="overflow-auto p-4 space-y-6">

            <div>

                <h2 className="font-bold text-lg">
                    {preview.filename}
                </h2>

            </div>

            <div>

                <h3 className="font-semibold">
                    Metadata
                </h3>

                <pre>

{JSON.stringify(preview.metadata, null, 2)}

                </pre>

            </div>

            <div>

                <h3 className="font-semibold">
                    Document Text
                </h3>

                <pre className="whitespace-pre-wrap">

                    {preview.text}

                </pre>

            </div>

            {

                preview.tables?.map(

                    (table, index) => (

                        <table
                            key={index}
                            className="border"
                        >

                            <tbody>

                                {

                                    table.map(

                                        (row, i) => (

                                            <tr key={i}>

                                                {

                                                    row.map(

                                                        (cell, j) => (

                                                            <td
                                                                key={j}
                                                                className="border p-2"
                                                            >

                                                                {cell}

                                                            </td>

                                                        )

                                                    )

                                                }

                                            </tr>

                                        )

                                    )

                                }

                            </tbody>

                        </table>

                    )

                )

            }

            <div className="grid grid-cols-3 gap-4">

                {

                    preview.images?.map(

                        image => (

                            <img

                                key={image.name}

                                src={image.previewUrl}

                                alt={image.name}

                            />

                        )

                    )

                }

            </div>

        </div>

    );

}