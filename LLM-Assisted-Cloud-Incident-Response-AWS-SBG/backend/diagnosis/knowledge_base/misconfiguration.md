# Runbook: Misconfiguration & Security Non-Compliance Incident Response

## 1. Overview
This runbook covers incidents categorized under the `misconfiguration` fault class. This includes AWS Config compliance rule failures (e.g. `S3_BUCKET_PUBLIC_READ_PROHIBITED`, `IAM_POLICY_NO_STATEMENTS_WITH_ADMIN_ACCESS`) and AWS GuardDuty security threat findings (e.g. unauthorized IP callers, suspicious IAM key usage, public exposure).

## 2. Diagnostic Steps
1. **Analyze AWS Config Compliance / Finding Data:**
   - Identify the flagged resource ID (e.g., S3 bucket name, IAM Role/Policy name, EC2 instance ID).
   - Check the exact compliance rule name and recorded evaluation result annotation.
2. **Inspect Resource Configuration History:**
   - Check AWS Config configuration items to determine when the misconfiguration was introduced and by which IAM principal/tag set.
3. **Review GuardDuty Finding Detail (if applicable):**
   - Examine finding severity rating (High / Medium / Low), actor IP address, and API call details.

## 3. Recommended Remediation Actions
- **`lock_s3_bucket`**: If an S3 bucket is flagged for public read/write permission or public policy grant (`S3_BUCKET_PUBLIC_READ_PROHIBITED`), immediately enable S3 Public Access Block on the bucket.
- **`tighten_iam_policy`**: If an IAM policy or role contains unconstrained wildcard permissions (`IAM_POLICY_NO_STATEMENTS_WITH_ADMIN_ACCESS` or `Action: *` / `Resource: *`), detach the overly permissive policy and attach the constrained standard policy.
- **`manual_review_required`**: If the finding indicates potentially compromised credentials or complex network security group changes requiring architectural review, flag for manual security analyst investigation.
