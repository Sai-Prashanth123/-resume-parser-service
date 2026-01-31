
import io, fitz
from PIL import Image
import pytesseract
from app.s3_client import get_s3_for_bucket
from docx import Document
from urllib.request import urlopen
from urllib.error import URLError, HTTPError

def _download_bytes_from_presigned_url(url: str) -> bytes:
    try:
        with urlopen(url, timeout=60) as resp:
            return resp.read()
    except HTTPError as e:
        raise RuntimeError(f"Failed to download resume (HTTP {e.code})") from e
    except URLError as e:
        raise RuntimeError("Failed to download resume (network error)") from e

def extract_text(payload):
    # Preferred: use pre-signed URL provided by profile-service (no AWS creds needed here)
    presigned = payload.get("s3PresignedUrl") or payload.get("presignedUrl") or payload.get("s3Url")
    if presigned:
        data = _download_bytes_from_presigned_url(presigned)
    else:
        bucket = payload["s3Bucket"]
        key = payload["s3Key"]
        s3 = get_s3_for_bucket(bucket)
        obj = s3.get_object(Bucket=bucket, Key=key)
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
