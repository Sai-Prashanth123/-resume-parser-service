
import io, fitz
from PIL import Image
import pytesseract
from app.s3_client import get_s3
from docx import Document

def extract_text(payload):
    s3 = get_s3()
    obj = s3.get_object(Bucket=payload["s3Bucket"], Key=payload["s3Key"])
    data = obj["Body"].read()
    ft = payload["fileType"].upper()

    if ft == "PDF":
        doc = fitz.open(stream=data, filetype="pdf")
        return "\n".join(p.get_text() for p in doc)
    if ft == "DOCX":
        return "\n".join(p.text for p in Document(io.BytesIO(data)).paragraphs)
    if ft in ["JPG","PNG","JPEG"]:
        return pytesseract.image_to_string(Image.open(io.BytesIO(data)))
    return data.decode(errors="ignore")
