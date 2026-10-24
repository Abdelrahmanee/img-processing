import json
import os
import re
from decimal import Decimal

import boto3
from botocore.config import Config

s3 = boto3.client("s3", config=Config(signature_version="s3v4"))
table = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])
DEST_BUCKET = os.environ["DEST_BUCKET"]
CDN_DOMAIN = os.environ.get("CDN_DOMAIN", "")
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def _default(value):
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    raise TypeError


def _response(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json", "Cache-Control": "no-store"},
        "body": json.dumps(body, default=_default),
    }


def handler(event, context):
    image_id = (event.get("pathParameters") or {}).get("imageId", "")
    if not UUID_RE.match(image_id):
        return _response(400, {"error": "Invalid image id"})

    item = table.get_item(Key={"imageId": image_id}).get("Item")
    if not item:
        return _response(404, {"error": "Not found"})

    body = {"imageId": image_id, "status": item["status"]}
    if item["status"] == "COMPLETED":
        outputs = {}
        for name, out in item.get("outputs", {}).items():
            if CDN_DOMAIN:
                url = f"https://{CDN_DOMAIN}/{out['key']}"
            else:  # CloudFront disabled: short-lived pre-signed URL
                url = s3.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": DEST_BUCKET, "Key": out["key"]},
                    ExpiresIn=900,
                )
            outputs[name] = {"url": url, "width": out.get("width"), "height": out.get("height")}
        body["outputs"] = outputs
    elif item["status"] == "FAILED":
        body["error"] = "Image could not be processed"  # details stay in DynamoDB / logs
    return _response(200, body)
