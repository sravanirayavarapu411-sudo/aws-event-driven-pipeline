"""
The processing worker. In production this runs on an EC2 instance
(inside a private subnet, reaching AWS via a NAT Gateway) as a long-lived
process or systemd service. Here it runs locally against LocalStack -
the logic below is unchanged either way.

It:
  1. Long-polls the SQS queue for S3 upload-event messages
  2. Parses the S3 event to find which object was uploaded
  3. Writes a record to DynamoDB
  4. Publishes a completion message to SNS
  5. Deletes the SQS message once processing succeeds

Usage:
    python consumer.py
"""

import json
import time
import datetime as dt
from aws_clients import get_client, get_resource
from setup_infra import QUEUE_NAME, TABLE_NAME, TOPIC_NAME


def get_queue_url(sqs):
    return sqs.get_queue_url(QueueName=QUEUE_NAME)["QueueUrl"]


def get_topic_arn(sns):
    topics = sns.list_topics()["Topics"]
    for t in topics:
        if t["TopicArn"].endswith(f":{TOPIC_NAME}"):
            return t["TopicArn"]
    raise RuntimeError("SNS topic not found - did you run setup_infra.py?")


def process_message(body, table, sns, topic_arn):
    event = json.loads(body)

    # Real S3->SQS event notifications wrap the actual event in "Records".
    # LocalStack's test-event tooling sometimes sends a bare test payload -
    # handle both so the consumer doesn't crash on the initial "s3:TestEvent".
    if "Records" not in event:
        print("[Consumer] Skipping non-S3 test message")
        return

    for record in event["Records"]:
        bucket = record["s3"]["bucket"]["name"]
        key = record["s3"]["object"]["key"]
        size = record["s3"]["object"].get("size", 0)

        table.put_item(Item={
            "file_key": key,
            "bucket": bucket,
            "size_bytes": size,
            "processed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        })
        print(f"[Consumer] Wrote record for '{key}' to DynamoDB")

        sns.publish(
            TopicArn=topic_arn,
            Subject="File processed",
            Message=f"File '{key}' ({size} bytes) was uploaded and recorded successfully.",
        )
        print(f"[Consumer] Published SNS notification for '{key}'")


def main():
    sqs = get_client("sqs")
    sns = get_client("sns")
    ddb = get_resource("dynamodb")
    table = ddb.Table(TABLE_NAME)

    queue_url = get_queue_url(sqs)
    topic_arn = get_topic_arn(sns)

    print(f"[Consumer] Polling {queue_url} ... (Ctrl+C to stop)")
    while True:
        resp = sqs.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=5,
            WaitTimeSeconds=10,  # long polling
        )
        messages = resp.get("Messages", [])
        if not messages:
            continue

        for msg in messages:
            try:
                process_message(msg["Body"], table, sns, topic_arn)
            except Exception as exc:
                print(f"[Consumer] Failed to process message, leaving in queue: {exc}")
                continue
            sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=msg["ReceiptHandle"])


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[Consumer] Stopped.")
