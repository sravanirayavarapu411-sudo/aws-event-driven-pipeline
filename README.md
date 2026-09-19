# Event-Driven Upload Pipeline (AWS, tested locally with LocalStack)

A small event-driven pipeline that mirrors a real production pattern:

```
Client uploads file
        |
        v
    S3 bucket  --(event notification)-->  SQS queue
                                              |
                                              v
                                   Consumer (Python, boto3)
                                   [in prod: runs on EC2 in a
                                    private subnet via NAT Gateway]
                                              |
                              +---------------+---------------+
                              v                                v
                        DynamoDB table                   SNS topic
                       (processed record)              (completion alert)
```

**Why this design:** SQS decouples the upload event from processing, so the
consumer can be scaled, restarted, or fail without losing uploads. IAM is
scoped to least privilege (see `iam_least_privilege_policy.json`, generated
by `setup_infra.py`) rather than using broad/admin permissions.

## Why LocalStack

Built and tested against [LocalStack](https://www.localstack.cloud/) rather
than a real AWS account, so it costs nothing to develop and iterate on. The
code uses the standard `boto3` AWS SDK throughout — the only LocalStack-
specific line is the `endpoint_url` in `aws_clients.py`. Pointing that at
real AWS (and using a real IAM role instead of dummy credentials) is the
only change needed to run this in production.

## Prerequisites

- Docker + Docker Compose
- Python 3.9+
- A free LocalStack account and auth token (required as of LocalStack's March 2026
  image consolidation — sign up at https://app.localstack.cloud, generate a token
  under Auth Tokens, then set it before starting the container:
  `$env:LOCALSTACK_AUTH_TOKEN="your-token-here"` in PowerShell, or
  `export LOCALSTACK_AUTH_TOKEN=your-token-here` in bash/zsh.
  No payment details required — this only unlocks the free-tier services.

## Setup

```bash
# 1. Start LocalStack
docker compose up -d

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Provision the S3 bucket, SQS queue, DynamoDB table, and SNS topic
python setup_infra.py
```

## Run it

In one terminal, start the consumer (it long-polls SQS):

```bash
python consumer.py
```

In another terminal, upload a file to trigger the pipeline:

```bash
echo "hello world" > sample.txt
python producer.py sample.txt
```

You should see the consumer pick up the S3 event, write a record to
DynamoDB, and publish an SNS notification — all within a few seconds.

## Verify manually (optional)

```bash
# Check the DynamoDB record
aws --endpoint-url=http://localhost:4566 dynamodb scan --table-name ProcessedUploads

# List SNS topics
aws --endpoint-url=http://localhost:4566 sns list-topics
```//(requires the `awscli-local` or standard AWS CLI with `--endpoint-url`)

## What I'd add next

- Move the consumer into a VPC private subnet reachable only via a NAT
  Gateway (in progress — learning this now).
- Dead-letter queue (DLQ) on the SQS queue for messages that repeatedly fail.
- CloudWatch-equivalent logging/metrics.
- Infrastructure as code (Terraform/CloudFormation) instead of the
  `setup_infra.py` script, for a fully reproducible deploy.

## Verified working

This pipeline has been run end-to-end: file upload triggers the S3 event,
the consumer picks it up from SQS, writes the record to DynamoDB, and
publishes the SNS notification — confirmed via console output on a local
Windows + Docker Desktop + LocalStack setup.
