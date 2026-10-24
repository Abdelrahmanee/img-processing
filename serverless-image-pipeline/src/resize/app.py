import io
import os

import boto3
from PIL import Image, ImageOps

s3 = boto3.client("s3")
DEST_BUCKET = os.environ["DEST_BUCKET"]

# name -> longest edge in pixels. thumbnail() never upscales.
VARIANTS = {"thumbnail": 300, "full": 1920}


def handler(event, context):
    image_id = event["imageId"]
    data = s3.get_object(Bucket=event["bucket"], Key=event["key"])["Body"].read()

    variants = {}
    with Image.open(io.BytesIO(data)) as img:
        img = ImageOps.exif_transpose(img)
        has_alpha = "A" in img.getbands() or "transparency" in img.info
        img = img.convert("RGBA" if has_alpha else "RGB")

        for name, edge in VARIANTS.items():
            variant = img.copy()
            variant.thumbnail((edge, edge), Image.Resampling.LANCZOS)
            buf = io.BytesIO()
            variant.save(buf, "WEBP", quality=82)
            work_key = f"work/{image_id}/{name}.webp"
            s3.put_object(
                Bucket=DEST_BUCKET,
                Key=work_key,
                Body=buf.getvalue(),
                ContentType="image/webp",
            )
            variants[name] = {"workKey": work_key, "width": variant.width, "height": variant.height}

    return {**event, "variants": variants}
