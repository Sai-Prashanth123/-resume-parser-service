
import boto3
import os
from botocore.config import Config

# Simple in-process cache so we don't look up region repeatedly
_BUCKET_REGION_CACHE: dict[str, str] = {}

def get_s3():
    # Ensure region is respected (important when bucket is not us-east-1)
    region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
    if region:
        return boto3.client("s3", region_name=region, config=Config(signature_version="s3v4"))
    return boto3.client("s3", config=Config(signature_version="s3v4"))

def get_s3_for_bucket(bucket: str):
    """
    Create an S3 client pinned to the bucket's actual region.
    This avoids SignatureDoesNotMatch errors when the environment region differs.
    """
    if not bucket:
        return get_s3()

    if bucket in _BUCKET_REGION_CACHE:
        region = _BUCKET_REGION_CACHE[bucket]
        return boto3.client("s3", region_name=region, config=Config(signature_version="s3v4"))

    # GetBucketLocation is best called against us-east-1 and returns the bucket region.
    locator = boto3.client("s3", region_name="us-east-1", config=Config(signature_version="s3v4"))
    resp = locator.get_bucket_location(Bucket=bucket)
    loc = resp.get("LocationConstraint")

    # AWS returns None / "" for us-east-1
    region = loc or "us-east-1"
    _BUCKET_REGION_CACHE[bucket] = region
    return boto3.client("s3", region_name=region, config=Config(signature_version="s3v4"))
