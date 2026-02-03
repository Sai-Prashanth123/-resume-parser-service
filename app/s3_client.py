
import boto3
import os
from botocore.config import Config

_BUCKET_REGION_CACHE: dict[str, str] = {}

def get_s3():
    region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
    if region:
        return boto3.client("s3", region_name=region, config=Config(signature_version="s3v4"))
    return boto3.client("s3", config=Config(signature_version="s3v4"))

def get_s3_for_bucket(bucket: str):
    if not bucket:
        return get_s3()

    if bucket in _BUCKET_REGION_CACHE:
        region = _BUCKET_REGION_CACHE[bucket]
        return boto3.client("s3", region_name=region, config=Config(signature_version="s3v4"))

    locator = boto3.client("s3", region_name="us-east-1", config=Config(signature_version="s3v4"))
    resp = locator.get_bucket_location(Bucket=bucket)
    loc = resp.get("LocationConstraint")

    region = loc or "us-east-1"
    _BUCKET_REGION_CACHE[bucket] = region
    return boto3.client("s3", region_name=region, config=Config(signature_version="s3v4"))
