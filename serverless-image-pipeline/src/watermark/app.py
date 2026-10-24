import io
import os

import boto3
from PIL import Image, ImageDraw, ImageFont

s3 = boto3.client("s3")
DEST_BUCKET = os.environ["DEST_BUCKET"]
TEXT = os.environ.get("WATERMARK_TEXT", "")


def _watermark(img, text):
    base = img.convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    size = max(12, base.width // 25)
    font = ImageFont.load_default(size=size)  # requires Pillow >= 10.1
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    pad = max(8, size // 2)
    x = base.width - (right - left) - pad - left
    y = base.height - (bottom - top) - pad - top
    draw.text((x + 1, y + 1), text, font=font, fill=(0, 0, 0, 110))   # soft shadow
    draw.text((x, y), text, font=font, fill=(255, 255, 255, 170))
    return Image.alpha_composite(base, overlay)


def handler(event, context):
    image_id = event["imageId"]
    outputs = {}
    for name, variant in event["variants"].items():
        body = s3.get_object(Bucket=DEST_BUCKET, Key=variant["workKey"])["Body"].read()
        with Image.open(io.BytesIO(body)) as img:
            result = _watermark(img, TEXT) if TEXT else img.convert("RGBA")
        buf = io.BytesIO()
        result.save(buf, "WEBP", quality=82)
        out_key = f"processed/{image_id}/{name}.webp"
        s3.put_object(
            Bucket=DEST_BUCKET,
            Key=out_key,
            Body=buf.getvalue(),
            ContentType="image/webp",
            # Key contains a unique imageId, so the object never changes: cache aggressively.
            CacheControl="public, max-age=31536000, immutable",
        )
        outputs[name] = {"key": out_key, "width": variant["width"], "height": variant["height"]}
    return {**event, "outputs": outputs}
