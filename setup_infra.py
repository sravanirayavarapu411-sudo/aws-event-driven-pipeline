"""
Provisions the pipeline's infrastructure against LocalStack:

    S3 bucket  --(event notification)-->  SQS queue
    DynamoDB table (for processed records)
    SNS topic (for completion alerts)
    A least-privilege IAM policy document (for realism / interview talking point)

Run this once before producer.py / consumer.py.
"""

import json
from aws_clients import get_client, get_resource

BUCKET_NAME = "upload-pipeline-bucket"
QUEUE_NAME = "upload-events-queue"
TABLE_NAME = "ProcessedUploads"
TOPIC_NAME = "upload-completion-topic"


def create_s3_bucket():
    s3 = get_client("s3")
    s3.create_bucket(Bucket=BUCKET_NAME)
    print(f"[S3] Bucket ready: {BUCKET_NAME}")


def create_sqs_queue():
    sqs = get_client("sqs")
    resp = sqs.create_queue(QueueName=QUEUE_NAME)
    queue_url = resp["QueueUrl"]
    attrs = sqs.get_queue_attributes(QueueUrl=queue_url, AttributeNames=["QueueArn"])
    queue_arn = attrs["Attributes"]["QueueArn"]

    # Allow the S3 bucket to send messages to this queue.
    policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": "*",
            "Action": "sqs:SendMessage",
            "Resource": queue_arn,
            "Condition": {"ArnLike": {"aws:SourceArn": f"arn:aws:s3:::{BUCKET_NAME}"}},
        }],
    }
    sqs.set_queue_attributes(QueueUrl=queue_url, Attributes={"Policy": json.dumps(policy)})
    print(f"[SQS] Queue ready: {queue_url}")
    return queue_url, queue_arn


def wire_s3_to_sqs(queue_arn):
    s3 = get_client("s3")
    s3.put_bucket_notification_configuration(
        Bucket=BUCKET_NAME,
        NotificationConfiguration={
            "QueueConfigurations": [{
                "QueueArn": queue_arn,
                "Events": ["s3:ObjectCreated:*"],
            }]
        },
    )
    print("[S3] Event notification -> SQS wired up")


def create_dynamodb_table():
    ddb = get_resource("dynamodb")
    ddb.create_table(
        TableName=TABLE_NAME,
        KeySchema=[{"AttributeName": "file_key", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "file_key", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    print(f"[DynamoDB] Table ready: {TABLE_NAME}")


def create_sns_topic():
    sns = get_client("sns")
    resp = sns.create_topic(Name=TOPIC_NAME)
    topic_arn = resp["TopicArn"]
    print(f"[SNS] Topic ready: {topic_arn}")
    # Subscribe an email endpoint for a real deploy, e.g.:
    # sns.subscribe(TopicArn=topic_arn, Protocol="email", Endpoint="you@example.com")
    return topic_arn


def write_least_privilege_policy_doc():
    """
    LocalStack Community doesn't enforce IAM, but writing this out is exactly
    what you'd hand to a real AWS account - and it's a strong interview point:
    scoped to only the 4 resources this pipeline touches, nothing broader.
    """
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {"Effect": "Allow", "Action": ["s3:GetObject", "s3:PutObject"],
             "Resource": f"arn:aws:s3:::{BUCKET_NAME}/*"},
            {"Effect": "Allow", "Action": ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"],
             "Resource": f"arn:aws:sqs:*:*:{QUEUE_NAME}"},
            {"Effect": "Allow", "Action": ["dynamodb:PutItem"],
             "Resource": f"arn:aws:dynamodb:*:*:table/{TABLE_NAME}"},
            {"Effect": "Allow", "Action": ["sns:Publish"],
             "Resource": f"arn:aws:sns:*:*:{TOPIC_NAME}"},
        ],
    }
    with open("iam_least_privilege_policy.json", "w") as f:
        json.dump(policy, f, indent=2)
    print("[IAM] Least-privilege policy document written to iam_least_privilege_policy.json")


if __name__ == "__main__":
    create_s3_bucket()
    queue_url, queue_arn = create_sqs_queue()
    wire_s3_to_sqs(queue_arn)
    create_dynamodb_table()
    topic_arn = create_sns_topic()
    write_least_privilege_policy_doc()

    print("\nAll infra created. Save these for producer.py / consumer.py:")
    print(f"  BUCKET_NAME = {BUCKET_NAME!r}")
    print(f"  QUEUE_URL   = {queue_url!r}")
    print(f"  TABLE_NAME  = {TABLE_NAME!r}")
    print(f"  TOPIC_ARN   = {topic_arn!r}")
