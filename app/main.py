
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from app.parsing.pipeline import parse_resume
import re
import logging
import json
import os

from botocore.exceptions import NoCredentialsError, ClientError

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

app = FastAPI(title="Resume Parser (Parse-Only)")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("resume-parser")
logger.setLevel(logging.INFO)
logger.propagate = True

class ParseRequest(BaseModel):
    userId: str
    resumeId: str
    s3Bucket: str
    s3Key: str
    fileType: str
    s3PresignedUrl: str | None = None

def _normalize_file_type(file_type: str | None) -> str:
    if not file_type:
        raise HTTPException(status_code=400, detail="fileType is required")
    ft = (file_type or "").strip()
    if not ft:
        raise HTTPException(status_code=400, detail="fileType is required")

    ft_lower = ft.lower()
    if "/" in ft_lower:
        if ft_lower == "application/pdf":
            return "PDF"
        if ft_lower == "application/msword" or "msword" in ft_lower:
            return "DOC"
        if "officedocument.wordprocessingml.document" in ft_lower or "wordprocessingml" in ft_lower:
            return "DOCX"
        if "image/png" in ft_lower or ft_lower.endswith("png"):
            return "PNG"
        if "image/jpeg" in ft_lower or "image/jpg" in ft_lower or "jpeg" in ft_lower or "jpg" in ft_lower:
            return "JPG"

    token = ft_lower[1:] if ft_lower.startswith(".") else ft_lower
    if token in {"pdf", "docx", "doc", "png", "jpg", "jpeg"}:
        return token.upper() if token != "jpeg" else "JPEG"

    upper = ft.upper()
    if upper in {"PDF", "DOCX", "DOC", "PNG", "JPG", "JPEG"}:
        return upper

    raise HTTPException(status_code=400, detail=f"Unsupported fileType: {file_type}")

def _validate_request(req: ParseRequest):
    if req.s3PresignedUrl:
        return
    if not re.search(rf"(^|/){re.escape(req.userId)}(/|$)", req.s3Key):
        raise HTTPException(
            status_code=400,
            detail="s3Key does not appear to belong to the provided userId"
        )

@app.post("/v1/parse")
def parse_v1(req: ParseRequest):
    try:
        _validate_request(req)
        payload = req.dict()
        payload["fileType"] = _normalize_file_type(req.fileType)

        logger.info("Parse request userId=%s resumeId=%s fileType=%s s3Bucket=%s s3Key=%s presigned=%s",
                    req.userId, req.resumeId, payload["fileType"], req.s3Bucket, req.s3Key, bool(req.s3PresignedUrl))
        print(f"PARSE_REQUEST userId={req.userId} resumeId={req.resumeId} fileType={payload['fileType']} s3Key={req.s3Key}", flush=True)

        if payload["fileType"] == "DOC":
            raise HTTPException(status_code=400, detail="Legacy .doc files are not supported. Please upload a .docx file.")

        result = parse_resume(payload)

        max_chars = int(os.getenv("RESUME_PARSER_LOG_RESPONSE_CHARS", "12000"))
        try:
            dumped = json.dumps(result, ensure_ascii=False)
            snippet = dumped if max_chars <= 0 else dumped[:max_chars]
            logger.info("Parsed resume userId=%s resumeId=%s response=%s", req.userId, req.resumeId, snippet)
            print(f"PARSED_RESUME_JSON userId={req.userId} resumeId={req.resumeId} {snippet}", flush=True)
        except Exception:
            logger.info("Parsed resume userId=%s resumeId=%s (response not JSON-serializable)", req.userId, req.resumeId)
        return result
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except NoCredentialsError:
        logger.exception("AWS credentials not found")
        raise HTTPException(status_code=401, detail="AWS credentials not configured for resume-parser-service")
    except ClientError as e:
        code = (e.response.get("Error", {}) or {}).get("Code", "ClientError")
        msg = (e.response.get("Error", {}) or {}).get("Message", str(e))
        logger.exception("AWS ClientError: %s %s", code, msg)
        if code in {"NoSuchKey", "NoSuchBucket"}:
            raise HTTPException(status_code=404, detail=f"S3 not found: {code}")
        if code in {"AccessDenied"}:
            raise HTTPException(status_code=403, detail="S3 access denied for resume-parser-service")
        if code in {"InvalidAccessKeyId", "SignatureDoesNotMatch"}:
            raise HTTPException(status_code=401, detail=f"AWS credentials error: {code}")
        raise HTTPException(status_code=400, detail=f"AWS error: {code}")
    except Exception as e:
        logger.exception("Unhandled error in /v1/parse")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/parse")
def parse_alias(req: ParseRequest):
    return parse_v1(req)

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/ready")
def ready():
    return {"ready": True}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", reload=True, port=6000)
