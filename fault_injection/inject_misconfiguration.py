#!/usr/bin/env python3
"""
Fault Injection Script: Misconfiguration
Simulates or removes S3 Public Access Block or emits AWS Config non-compliance event.
"""

import argparse
import datetime
import json
import logging
import os
import sys

try:
    import boto3
except (ImportError, AttributeError, Exception):
    boto3 = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def inject_misconfiguration(
    environment: str = "dev",
    region: str = "ap-south-1",
    dry_run: bool = False,
    bucket_name: str | None = None,
    rule_name: str = "s3-bucket-level-public-access-prohibited",
) -> dict:
    env = environment
    if not bucket_name:
        if env != "dev":
            account_id = "889081505756"
            bucket_name = f"llm-incident-datalake-{account_id}-{env}"
        else:
            bucket_name = os.environ.get("DATA_LAKE_BUCKET")
    if not bucket_name:
        account_id = "889081505756"
        if boto3 is not None and not dry_run:
            try:
                account_id = boto3.client("sts", region_name=region).get_caller_identity()["Account"]
            except Exception:
                pass
        bucket_name = f"llm-incident-datalake-{account_id}-{env}"
    target_bucket = bucket_name
    injected_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

    logger.info(f"Injecting misconfiguration fault: bucket={target_bucket}, rule={rule_name}, dry_run={dry_run}")

    if dry_run:
        result = {
            "fault_class": "misconfiguration",
            "target_resource": target_bucket,
            "config_rule_name": rule_name,
            "injected_at": injected_at,
            "status": "simulated_injection",
            "dry_run": True,
        }
        logger.info(f"Dry-run injection completed: {json.dumps(result)}")
        return result

    if boto3 is None:
        raise RuntimeError("boto3 is required for live AWS fault injection. Install boto3 or run with --dry-run.")

    try:
        s3_client = boto3.client("s3", region_name=region)
        s3_client.delete_public_access_block(Bucket=target_bucket)
        status = "removed_public_access_block"
    except Exception as exc:
        logger.warning(f"Failed to delete public access block on bucket {target_bucket} ({exc}); attempting Config evaluation trigger.")
        try:
            config_client = boto3.client("config", region_name=region)
            config_client.start_config_rules_evaluation(ConfigRuleNames=[rule_name])
            status = "triggered_config_evaluation"
        except Exception as config_exc:
            logger.warning(f"Config evaluation trigger failed ({config_exc}); recording injection attempt.")
            status = f"injection_attempted_failed: {exc}"

    result = {
        "fault_class": "misconfiguration",
        "target_resource": target_bucket,
        "config_rule_name": rule_name,
        "injected_at": injected_at,
        "status": status,
        "dry_run": False,
    }
    logger.info(f"Fault injection output: {json.dumps(result)}")
    return result


def main():
    parser = argparse.ArgumentParser(description="Inject Misconfiguration fault into AWS environment")
    parser.add_argument("--environment", default="dev", help="Environment stage (e.g. dev, prod)")
    parser.add_argument("--region", default="ap-south-1", help="AWS region")
    parser.add_argument("--bucket-name", help="Target S3 bucket name")
    parser.add_argument("--rule-name", default="s3-bucket-level-public-access-prohibited", help="AWS Config rule name")
    parser.add_argument("--dry-run", action="store_true", help="Simulate injection without altering AWS state")

    args = parser.parse_args()

    try:
        res = inject_misconfiguration(
            environment=args.environment,
            region=args.region,
            dry_run=args.dry_run,
            bucket_name=args.bucket_name,
            rule_name=args.rule_name,
        )
        print(json.dumps(res, indent=2))
    except Exception as exc:
        logger.error(f"Fault injection failed: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
