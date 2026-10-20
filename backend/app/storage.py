from functools import lru_cache
from typing import Any

import boto3
from botocore.config import Config

from app.config import settings


@lru_cache
def s3(public: bool = False) -> Any:
    cfg = settings()
    return boto3.client(
        "s3",
        region_name=cfg.aws_region,
        endpoint_url=(cfg.s3_public_endpoint if public else cfg.s3_endpoint) or None,
        config=Config(
            signature_version="s3v4",
            retries={"total_max_attempts": 3, "mode": "standard"},
            connect_timeout=5,
            read_timeout=30,
            s3={"addressing_style": "path"},
        ),
    )
