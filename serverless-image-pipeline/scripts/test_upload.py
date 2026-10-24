"""End-to-end smoke test using only the standard library.

Usage:
  python scripts/test_upload.py <UploadUrlEndpoint> <CloudFrontDomain|none> path/to/image.jpg
"""
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.request


def main(api_url, cdn_domain, path):
    content_type = mimetypes.guess_type(path)[0] or "image/jpeg"

    req = urllib.request.Request(
        api_url,
        data=json.dumps({"filename": os.path.basename(path), "contentType": content_type}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        info = json.load(resp)
    print("imageId:", info["imageId"])

    with open(path, "rb") as f:
        put = urllib.request.Request(
            info["uploadUrl"], data=f.read(), headers=info["headers"], method="PUT"
        )
        urllib.request.urlopen(put).read()
    print("Uploaded. Waiting for processing...")

    if cdn_domain.lower() == "none":
        print("CloudFront is disabled. Check the results with:")
        print(f"  aws s3 ls s3://<DestinationBucketName>/processed/{info['imageId']}/")
        return

    for name in ("thumbnail", "full"):
        url = f"https://{cdn_domain}/processed/{info['imageId']}/{name}.webp"
        for _ in range(30):
            try:
                with urllib.request.urlopen(urllib.request.Request(url, method="HEAD")) as r:
                    if r.status == 200:
                        print(f"READY  {url}")
                        break
            except urllib.error.HTTPError:
                pass
            time.sleep(2)
        else:
            print(f"Timed out waiting for {url} - check Step Functions and the DLQ")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])
