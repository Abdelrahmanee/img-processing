import json
import os
from urllib.parse import unquote_plus

import boto3

sfn = boto3.client("stepfunctions")
STATE_MACHINE_ARN = os.environ["STATE_MACHINE_ARN"]


def handler(event, context):
    """SQS consumer: one Step Functions execution per uploaded image.

    Returns partial batch failures so only the failed messages are retried
    (and eventually land in the DLQ).
    """
    failures = []
    for record in event["Records"]:
        try:
            body = json.loads(record["body"])
            if body.get("Event") == "s3:TestEvent":  # sent once when notifications are configured
                continue
            for s3_record in body.get("Records", []):
                bucket = s3_record["s3"]["bucket"]["name"]
                key = unquote_plus(s3_record["s3"]["object"]["key"])
                image_id = key.split("/")[1]  # uploads/<imageId>/<filename>
                try:
                    sfn.start_execution(
                        stateMachineArn=STATE_MACHINE_ARN,
                        # Deterministic name => duplicate SQS deliveries do not start duplicate workflows
                        name=image_id,
                        input=json.dumps({"imageId": image_id, "bucket": bucket, "key": key}),
                    )
                except sfn.exceptions.ExecutionAlreadyExists:
                    print(f"Execution already exists for {image_id}; skipping duplicate")
        except Exception as exc:  # noqa: BLE001
            print(f"Failed to process message {record['messageId']}: {exc}")
            failures.append({"itemIdentifier": record["messageId"]})
    return {"batchItemFailures": failures}
