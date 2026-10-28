import type { PreviewResult } from "../../types/preview";

interface Props {
    preview: PreviewResult;
}

export default function PptxViewer({ preview }: Props) {

    return (

        <div className="overflow-auto p-4 space-y-6">

            <h2 className="font-bold text-lg">

                {preview.filename}

            </h2>

            {

                preview.slides?.map(

                    slide => (

                        <div
                            key={slide.slide}
                        >

                            <h3>

                                Slide {slide.slide}

                            </h3>

                            <pre className="whitespace-pre-wrap">

                                {slide.text}

                            </pre>

                        </div>

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