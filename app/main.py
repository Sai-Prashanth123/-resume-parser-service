
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from app.parsing.pipeline import parse_resume
import re
import logging
import json
import os

from botocore.exceptions import NoCredentialsError, ClientError

# Load .env automatically for local dev (AWS creds, region, GROQ key, etc.)
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    # If python-dotenv isn't installed, env vars must be provided by the runtime
    pass

app = FastAPI(title="Resume Parser (Parse-Only)")
# Ensure INFO logs show up under uvicorn.
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
    # Optional: if provided, service downloads via HTTPS instead of using AWS creds
    s3PresignedUrl: str | None = None

def _validate_request(req: ParseRequest):
    # Basic safety: ensure the key is scoped to the userId folder (prevents mismatches)
    # Expected patterns: resumes/<userId>/... or .../<userId>/...
    # If a presigned URL is provided, skip key validation (still requires bucket/key in payload for audit)
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
        result = parse_resume(req.dict())

        # Print parsed response to logs (truncated) for debugging.
        # You can disable by setting RESUME_PARSER_LOG_RESPONSE=false
        if os.getenv("RESUME_PARSER_LOG_RESPONSE", "true").lower() in {"1", "true", "yes"}:
            try:
                dumped = json.dumps(result, ensure_ascii=False)
                logger.info("Parsed resume userId=%s resumeId=%s response=%s", req.userId, req.resumeId, dumped[:4000])
                # Fallback: some uvicorn setups may not show custom logger output.
                # Printing guarantees the response appears in the terminal.
                print(f"PARSED_RESUME_JSON userId={req.userId} resumeId={req.resumeId} {dumped[:4000]}", flush=True)
            except Exception:
                logger.info("Parsed resume userId=%s resumeId=%s (response not JSON-serializable)", req.userId, req.resumeId)
        return result
    except HTTPException:
        raise
    except NoCredentialsError:
        # AWS creds not present in this service environment
        logger.exception("AWS credentials not found")
        raise HTTPException(status_code=401, detail="AWS credentials not configured for resume-parser-service")
    except ClientError as e:
        # Common S3 errors: NoSuchKey, AccessDenied, InvalidAccessKeyId, etc.
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
        # Print full traceback to logs for debugging
        logger.exception("Unhandled error in /v1/parse")
        raise HTTPException(status_code=500, detail=str(e))

# Backwards/alternate path support (helps when gateway rewrites /parse)
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