import base64
import mimetypes
from .office_preview import OfficePreview


class PreviewBuilder:

    def __init__(self):
        self.office = OfficePreview()
    
    def build(self, evidence, data: bytes):

        mime, _ = mimetypes.guess_type(
            evidence.filename or ""
        )

        if mime is None:
            mime = "application/octet-stream"

        preview_type = self._preview_type(mime)

        if preview_type == "docx":
            return self.office.preview_docx(evidence, data)

        if preview_type == "pptx":
            return self.office.preview_pptx(evidence, data)

        result = {

            "success": True,

            "filename": evidence.filename,

            "size": evidence.file_size,

            "mime": mime,

            "type": preview_type,

            "content": self._content(
                mime,
                data
            )
        }

        # Add previewUrl for images
        if preview_type == "image":

            result["previewUrl"] = (
                f"data:{mime};base64,{result['content']}"
            )

        return result
    
    def _preview_type(
        self,
        mime
    ):

        if (
            mime.startswith("text")
            or mime.endswith("xml")
            or mime.endswith("+xml")
            or mime == "application/json"
        ):
            return "text"

        if mime.startswith("image"):
            return "image"

        if mime == "application/pdf":
            return "pdf"
 
        if mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            return "docx"

        if mime == "application/vnd.openxmlformats-officedocument.presentationml.presentation":
            return "pptx"

        return "binary"
    

    def _content(
        self,
        mime,
        data
    ):

        if (
            mime.startswith("text")
            or mime.endswith("xml")
            or mime.endswith("+xml")
            or mime == "application/json"
        ):

            return data.decode(
                "utf-8",
                errors="replace"
            )

        return base64.b64encode(
            data
        ).decode("ascii")