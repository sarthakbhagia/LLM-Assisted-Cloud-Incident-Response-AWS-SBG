#!/usr/bin/env python3
"""
Fault Injection Script: Resource Exhaustion
Simulates or triggers high CPU / execution duration load on Service A or triggers the CloudWatch Alarm.
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import sys

try:
    import boto3
except (ImportError, AttributeError, Exception):
    boto3 = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def inject_resource_exhaustion(
    environment: str = "dev",
    region: str = "ap-south-1",
    dry_run: bool = False,
    alarm_name: str | None = None,
    target_function: str | None = None,
) -> dict:
    env = environment
    alarm = alarm_name or f"incident-service-a-resource-exhaustion-{env}"
    target = target_function or f"incident-service-a-{env}"
    injected_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

    logger.info(f"Injecting resource exhaustion fault: alarm={alarm}, target={target}, dry_run={dry_run}")

    if dry_run:
        result = {
            "fault_class": "resource_exhaustion",
            "target_resource": target,
            "alarm_name": alarm,
            "injected_at": injected_at,
            "status": "simulated_injection",
            "dry_run": True,
        }
        logger.info(f"Dry-run injection completed: {json.dumps(result)}")
        return result

    if boto3 is None:
        raise RuntimeError("boto3 is required for live AWS fault injection. Install boto3 or run with --dry-run.")

    try:
        cw_client = boto3.client("cloudwatch", region_name=region)
        cw_client.set_alarm_state(
            AlarmName=alarm,
            StateValue="ALARM",
            StateReason="Injected fault: Resource exhaustion CPU/memory spike on Service A",
            StateReasonData=json.dumps({"injected_by": "fault_injection/inject_resource_exhaustion.py"}),
        )
        status = "injected_alarm_state"
    except Exception as exc:
        logger.warning(f"Failed to set CloudWatch alarm state ({exc}); falling back to simulated injection status.")
        status = f"injection_attempted_failed: {exc}"

    result = {
        "fault_class": "resource_exhaustion",
        "target_resource": target,
        "alarm_name": alarm,
        "injected_at": injected_at,
        "status": status,
        "dry_run": False,
    }
    logger.info(f"Fault injection output: {json.dumps(result)}")
    return result


def main():
    parser = argparse.ArgumentParser(description="Inject Resource Exhaustion fault into AWS environment")
    parser.add_argument("--environment", default="dev", help="Environment stage (e.g. dev, prod)")
    parser.add_argument("--region", default="ap-south-1", help="AWS region")
    parser.add_argument("--alarm-name", help="Custom CloudWatch alarm name")
    parser.add_argument("--target-function", help="Target Lambda function name")
    parser.add_argument("--dry-run", action="store_true", help="Simulate injection without altering AWS state")

    args = parser.parse_args()

    try:
        res = inject_resource_exhaustion(
            environment=args.environment,
            region=args.region,
            dry_run=args.dry_run,
            alarm_name=args.alarm_name,
            target_function=args.target_function,
        )
        print(json.dumps(res, indent=2))
    except Exception as exc:
        logger.error(f"Fault injection failed: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
