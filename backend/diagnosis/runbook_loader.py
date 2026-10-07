"""
runbook_loader.py — Phase 4: Runbook Context Loader

Loads runbook text for the given fault_class from S3 (production) or local filesystem (development).
"""

import logging
import os
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def load_runbook(fault_class: str) -> tuple[str, str]:
    """
    Load the runbook text for the given fault_class.

    Priority:
    1. S3: s3://$DATA_LAKE_BUCKET/runbooks/<fault_class>.md (production)
    2. Local filesystem: ./knowledge_base/<fault_class>.md (development)
    3. Packaged fallback (if included in Lambda deployment package)
    4. Default runbook

    Returns a tuple of (runbook_content, runbook_source) where runbook_source is
    one of: "s3", "local", "packaged", "none".
    """
    filename = f"{fault_class}.md"

    # 1. Try S3 first (production)
    data_lake_bucket = os.environ.get("DATA_LAKE_BUCKET")
    if data_lake_bucket:
        s3_key = f"runbooks/{filename}"
        try:
            s3 = boto3.client("s3")
            resp = s3.get_object(Bucket=data_lake_bucket, Key=s3_key)
            content = resp["Body"].read().decode("utf-8")
            logger.info(f"Loaded runbook for {fault_class} from S3: s3://{data_lake_bucket}/{s3_key}")
            return content, "s3"
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            if error_code != "NoSuchKey":
                logger.warning(f"S3 error loading runbook {s3_key}: {exc}")
            # Fall through to local filesystem

    # 2. Try local filesystem (development)
    module_dir = Path(__file__).resolve().parent
    candidate_paths = [
        module_dir / "knowledge_base" / filename,
        module_dir.parent.parent / "knowledge_base" / filename,
        Path(os.getcwd()) / "knowledge_base" / filename,
    ]

    for path in candidate_paths:
        if path.is_file():
            try:
                content = path.read_text(encoding="utf-8")
                logger.info(f"Loaded runbook for {fault_class} from local filesystem: {path}")
                return content, "local"
            except Exception as exc:  # noqa: BLE001
                logger.error(f"Failed to read runbook at {path}: {exc}")

    # 3. Try packaged fallback (if runbooks are included in Lambda package)
    # This would be at /var/task/knowledge_base/ in the Lambda runtime
    packaged_path = Path("/var/task/knowledge_base") / filename
    if packaged_path.is_file():
        try:
            content = packaged_path.read_text(encoding="utf-8")
            logger.info(f"Loaded runbook for {fault_class} from packaged fallback: {packaged_path}")
            return content, "packaged"
        except Exception as exc:
            logger.error(f"Failed to read packaged runbook at {packaged_path}: {exc}")

    logger.warning(f"No runbook file found for fault_class={fault_class}")
    return f"# Default Runbook for {fault_class}\nNo specific runbook available.", "none"