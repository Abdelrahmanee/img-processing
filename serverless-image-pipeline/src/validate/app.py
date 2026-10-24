import io
import os
from datetime import datetime, timezone

import boto3
from PIL import Image, UnidentifiedImageError

Image.MAX_IMAGE_PIXELS = 50_000_000  # guard against decompression bombs

s3 = boto3.client("s3")
table = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])
MAX_BYTES = int(os.environ.get("MAX_IMAGE_BYTES", 15 * 1024 * 1024))
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


class ValidationError(Exception):
    pass


def handler(event, context):
    bucket, key, image_id = event["bucket"], event["key"], event["imageId"]

    size = s3.head_object(Bucket=bucket, Key=key)["ContentLength"]
    if size > MAX_BYTES:
        raise ValidationError(f"File is {size} bytes; limit is {MAX_BYTES}")

    data = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
    try:
        with Image.open(io.BytesIO(data)) as img:
            img.verify()
        with Image.open(io.BytesIO(data)) as img:
            fmt, (width, height) = img.format, img.size
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValidationError(f"Not a valid, supported image: {exc}") from exc

    if fmt not in ALLOWED_FORMATS:
        raise ValidationError(f"Unsupported format {fmt}")

    table.update_item(
        Key={"imageId": image_id},
        UpdateExpression=(
            "SET #s = :s, sourceKey = :k, width = :w, height = :h, "
            "sizeBytes = :b, #f = :f, updatedAt = :t"
        ),
        ExpressionAttributeNames={"#s": "status", "#f": "format"},
        ExpressionAttributeValues={
            ":s": "PROCESSING",
            ":k": key,
            ":w": width,
            ":h": height,
            ":b": size,
            ":f": fmt,
            ":t": datetime.now(timezone.utc).isoformat(),
        },
    )
    return {**event, "width": width, "height": height, "format": fmt, "sizeBytes": size}
