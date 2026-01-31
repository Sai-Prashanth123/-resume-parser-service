
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from app.parsing.pipeline import parse_resume

app = FastAPI(title="Resume Parser (Parse-Only)")

class ParseRequest(BaseModel):
    userId: str
    resumeId: str
    s3Bucket: str
    s3Key: str
    fileType: str

@app.post("/v1/parse")
def parse(req: ParseRequest):
    try:
        result = parse_resume(req.dict())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/ready")
def ready():
    return {"ready": True}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", reload=True, port=8084)