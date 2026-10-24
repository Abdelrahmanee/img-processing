import os
from datetime import datetime, timezone

import boto3
from botocore.config import Config

s3 = boto3.client("s3", config=Config(signature_version="s3v4"))
table = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])
DEST_BUCKET = os.environ["DEST_BUCKET"]
CDN_DOMAIN = os.environ.get("CDN_DOMAIN", "")


def handler(event, context):
    image_id = event["imageId"]

    outputs = {}
    for name, out in event["outputs"].items():
        s3.head_object(Bucket=DEST_BUCKET, Key=out["key"])  # confirm it really exists
        if CDN_DOMAIN:
            url = f"https://{CDN_DOMAIN}/{out['key']}"
        else:  # CloudFront disabled: fall back to a temporary pre-signed URL
            url = s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": DEST_BUCKET, "Key": out["key"]},
                ExpiresIn=3600,
            )
        outputs[name] = {**out, "url": url}

    # Clean up intermediate files (the lifecycle rule is the safety net)
    s3.delete_objects(
        Bucket=DEST_BUCKET,
        Delete={"Objects": [{"Key": v["workKey"]} for v in event["variants"].values()]},
    )

    table.update_item(
        Key={"imageId": image_id},
        UpdateExpression="SET #s = :s, outputs = :o, updatedAt = :t",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":s": "COMPLETED",
            ":o": outputs,
            ":t": datetime.now(timezone.utc).isoformat(),
        },
    )
    return {"imageId": image_id, "status": "COMPLETED", "outputs": outputs}
