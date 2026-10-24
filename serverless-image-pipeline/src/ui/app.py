import os

with open(os.path.join(os.path.dirname(__file__), "index.html"), encoding="utf-8") as f:
    PAGE = f.read()


def handler(event, context):
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-cache"},
        "body": PAGE,
    }
