# Required IAM Permissions for Phase 6 Deployment

## Summary

The IAM user `incident-response-om` (ARN: `arn:aws:iam::889081505756:user/incident-response-om`)
is missing permissions that CloudFormation needs to deploy Phase 4, 5, and 6 resources.
Without these permissions, every `sam deploy` fails.

> [!CAUTION]
> The stack is currently in `UPDATE_FAILED` state (a known stable state with `disable_rollback = true`).
> After the permissions are granted, run the deploy command once and it will succeed.

---

## Permissions Needed and Why

| Permission | Resource | Why It Is Needed |
|---|---|---|
| `iam:PutRolePolicy` | `*` | CloudFormation needs this to add new inline policies to existing roles when deploying Phase 4-5 Lambda updates (`CollectorDiagnosisRole`, `DemoAppRole` need new policies for Bedrock, downstream invoke) |
| `iam:DeleteRolePolicy` | `*` | CloudFormation calls this during updates and rollbacks to reconcile policy sets on existing roles |
| `iam:CreateRole` | `*` | CloudFormation needs this to create `ReportingApprovalRole` (Phase 5, not yet deployed) |
| `iam:PassRole` | `arn:aws:iam::889081505756:role/incident-remediation-role-dev` | CloudFormation needs this to assign `RemediationRole` to the new `RemediationFunction` and `VerificationFunction` Lambda functions |

---

## Policy JSON to Add

Ask your supervisor to attach the following inline policy to the `incident-response-om` IAM user
(or create a new managed policy and attach it):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "CloudFormationIAMDeploy",
      "Effect": "Allow",
      "Action": [
        "iam:PutRolePolicy",
        "iam:DeleteRolePolicy",
        "iam:CreateRole",
        "iam:DeleteRole",
        "iam:AttachRolePolicy",
        "iam:DetachRolePolicy",
        "iam:GetRole",
        "iam:GetRolePolicy",
        "iam:ListRolePolicies",
        "iam:ListAttachedRolePolicies",
        "iam:TagRole",
        "iam:UntagRole"
      ],
      "Resource": "*"
    },
    {
      "Sid": "PassRoleToLambdaAndCloudFormation",
      "Effect": "Allow",
      "Action": "iam:PassRole",
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "iam:PassedToService": [
            "lambda.amazonaws.com",
            "cloudformation.amazonaws.com"
          ]
        }
      }
    }
  ]
}
```

> [!NOTE]
> The `iam:PassRole` is scoped to only allow passing roles to Lambda and CloudFormation services.
> This is the standard minimal set for a CloudFormation deployer user.

---

## How to Add (AWS Console)

1. Go to IAM > Users > `incident-response-om`
2. Click "Add permissions" > "Attach policies directly" > "Create inline policy"
3. Switch to the JSON editor and paste the policy above
4. Name it `cloudformation-iam-deploy-permissions`
5. Click "Create policy"

---

## After Permissions Are Granted

Run the deploy once from the `infra/` directory:

```powershell
sam build
sam deploy --no-confirm-changeset --no-resolve-s3 --s3-bucket aws-sam-cli-managed-default-samclisourcebucket-kx2gwyhouegw --s3-prefix llm-incident-response
```

The changeset will:
- Create `DiagnosisFunction`, `NotifyFunction`, `ApprovalFunction`, `ReportingApprovalRole` (Phase 4-5 backfill)
- Create `RemediationFunction`, `VerificationFunction` (Phase 6-6.5)
- Update `CollectorDiagnosisRole` and `DemoAppRole` with new Phase 4-5 policies
- Wire `REMEDIATION_FUNCTION_NAME` in `ApprovalFunction`

Expected final stack status: `UPDATE_COMPLETE`
