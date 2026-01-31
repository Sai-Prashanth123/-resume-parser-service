
import boto3

def get_s3():
    return boto3.client("s3")
