"""
Shared boto3 client/resource factory pointed at LocalStack.

In production, you would delete the `endpoint_url` argument and rely on
real AWS credentials (e.g. an IAM role attached to the EC2 instance) -
every other line of code in this project stays identical. That's the
whole point of building against LocalStack: the code is AWS-compatible
from day one.
"""

import boto3

LOCALSTACK_ENDPOINT = "http://localhost:4566"
REGION = "us-east-1"

# LocalStack doesn't check these credentials, but boto3 requires *some*
# values to be present before it will let you make a call.
DUMMY_CREDS = {
    "aws_access_key_id": "test",
    "aws_secret_access_key": "test",
}


def get_client(service_name):
    return boto3.client(
        service_name,
        endpoint_url=LOCALSTACK_ENDPOINT,
        region_name=REGION,
        **DUMMY_CREDS,
    )


def get_resource(service_name):
    return boto3.resource(
        service_name,
        endpoint_url=LOCALSTACK_ENDPOINT,
        region_name=REGION,
        **DUMMY_CREDS,
    )
