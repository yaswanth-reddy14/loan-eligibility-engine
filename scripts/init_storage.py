"""Local-only MinIO bootstrap; no AWS resources are provisioned."""

import time

from app.config import settings
from app.storage import s3


def main() -> None:
    if not settings().s3_endpoint:
        raise RuntimeError("Local endpoint is required")
    client = s3()
    for attempt in range(20):
        try:
            client.list_buckets()
            break
        except Exception:
            if attempt == 19:
                raise
            time.sleep(1)
    existing = {bucket["Name"] for bucket in client.list_buckets()["Buckets"]}
    bucket = settings().s3_bucket
    if bucket not in existing:
        client.create_bucket(Bucket=bucket)
    client.put_bucket_versioning(Bucket=bucket, VersioningConfiguration={"Status": "Enabled"})
    # MinIO handles CORS using MINIO_API_CORS_ALLOW_ORIGIN or its default wildcard.
    # The presigned request is bound to key, headers and content length.
    print("Local versioned object bucket is ready")


if __name__ == "__main__":
    main()
