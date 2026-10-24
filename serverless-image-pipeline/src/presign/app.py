import json
import os
import re
import uuid
from datetime import datetime, timezone

import boto3
from botocore.config import Config

s3 = boto3.client("s3", config=Config(signature_version="s3v4"))
table = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])
SOURCE_BUCKET = os.environ["SOURCE_BUCKET"]
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
URL_TTL_SECONDS = 300


def _response(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def handler(event, context):
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return _response(400, {"error": "Body must be valid JSON"})

    content_type = body.get("contentType", "image/jpeg")
    if content_type not in ALLOWED_TYPES:
        return _response(400, {"error": f"contentType must be one of {sorted(ALLOWED_TYPES)}"})

    filename = re.sub(r"[^A-Za-z0-9._-]", "_", body.get("filename", "image"))[:100] or "image"
    image_id = str(uuid.uuid4())
    key = f"uploads/{image_id}/{filename}"

    upload_url = s3.generate_presigned_url(
        "put_object",
        Params={"Bucket": SOURCE_BUCKET, "Key": key, "ContentType": content_type},
        ExpiresIn=URL_TTL_SECONDS,
    )

    now = datetime.now(timezone.utc).isoformat()
    table.put_item(
        Item={
            "imageId": image_id,
            "status": "PENDING",
            "sourceKey": key,
            "createdAt": now,
            "updatedAt": now,
        }
    )

    return _response(
        200,
        {
            "imageId": image_id,
            "uploadUrl": upload_url,
            "method": "PUT",
            "headers": {"Content-Type": content_type},
            "expiresInSeconds": URL_TTL_SECONDS,
        },
    )
