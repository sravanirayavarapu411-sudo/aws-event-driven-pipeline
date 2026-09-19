"""
Simulates a client uploading a file to S3. This is the event that
kicks off the whole pipeline (S3 -> SQS -> consumer -> DynamoDB -> SNS).

Usage:
    python producer.py myfile.txt
"""

import sys
import os
from aws_clients import get_client
from setup_infra import BUCKET_NAME


def upload_file(local_path):
    s3 = get_client("s3")
    key = os.path.basename(local_path)
    s3.upload_file(local_path, BUCKET_NAME, key)
    print(f"[Producer] Uploaded '{local_path}' to s3://{BUCKET_NAME}/{key}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python producer.py <path-to-file>")
        sys.exit(1)
    upload_file(sys.argv[1])
