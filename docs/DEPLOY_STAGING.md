# Deploying the hardened template to staging — safely

Target: update the **existing** `llm-incident-response-staging` CloudFormation stack
(ap-south-1) with the current `infra/template.yaml` on `swarali` — which adds the
pipeline DLQ + queue-depth alarm, the approved-state sweeper, the scheduler-based
verification, and (via code deployment) the dashboard pagination fix.

Everything below was verified against the live account on 2026-09-21.

---

## 0. Why this is not a plain `sam deploy`

| Trap | Detail | Status |
|---|---|---|
| **Wrong default stack** | `infra/samconfig.toml` deploys stack `llm-incident-response` with `Environment="dev"`. The staging stack is **`llm-incident-response-staging`** (discovered via its Lambda log groups). A naive deploy creates a *second parallel stack*. | Override stack name + Environment on every command |
| **Zombie dev stack** | Your own stack `llm-incident-response` (dev) is in `DELETE_FAILED` with 4 remnants (`ConfigDeliveryChannel`, 2 ConfigRules, `IncidentDataLake` bucket object gone). It **cannot be updated** and must not be reused for staging. | Leave it alone; optional cleanup at the end |
| **IAM permission gap** | User `incident-response-swarali` cannot `cloudformation:ListStacks` on other stacks and has no Lambda list/get. `CreateStack`/`UpdateStack`/`ExecuteChangeSet` will fail the same way unless permissions are added, **or another identity (the one that deployed originally) runs the deploy**. | Confirm before starting |
| **SAM CLI not installed** | `sam` is not on PATH. | Install (§1) |
| **`disable_rollback = true` in samconfig** | A failed update would leave the stack broken instead of rolling back. | Never use `--config-env default` for this deploy; rollback protection matters |
| **Deploying from a dirty tree** | Historical foot-gun (a shell command was once committed as a message). | `git status` must be clean |

## 1. One-time prerequisites

```bash
# SAM CLI (macOS)
brew install aws-sam-cli

# IAM: whoever deploys needs (minimally):
#   cloudformation:  CreateChangeSet, ExecuteChangeSet, DescribeChangeSet,
#                    DescribeStackEvents, DescribeStacks, ValidateTemplate, UpdateTerminationProtection
#   + create/update on: lambda, iam roles, dynamodb, sqs, sns, events, scheduler,
#     s3, apigateway, logs (the resource types the template manages)
# Simplest: the identity that originally deployed the stack runs this runbook.
```

## 2. Preflight (5 minutes)

```bash
cd <repo root>
git checkout swarali && git pull origin swarali
git status --short                        # MUST be empty

.venv312/bin/python -m pytest tests -q    # expect: 99 passed

aws sts get-caller-identity               # account 889081505756, region ap-south-1
aws cloudformation validate-template \
    --template-body file://infra/template.yaml
```

## 3. Build

```bash
cd infra && sam build
```

## 4. Changeset FIRST — review before anything executes

```bash
sam deploy --stack-name llm-incident-response-staging \
  --parameter-overrides \
      Environment=staging \
      ServiceBUrl="https://0wv3y5mpal.execute-api.ap-south-1.amazonaws.com/Prod/service-b" \
      ServiceCUrl="https://0wv3y5mpal.execute-api.ap-south-1.amazonaws.com/Prod/service-c" \
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
  --no-execute-changeset
```

Notes:
- `--no-execute-changeset` creates the changeset and **stops** — nothing is modified
  yet. SAM prints the changeset name/ARN and the exact `execute-change-set` command.
- The ServiceB/C URLs were verified live (HTTP 200 on `/Prod/service-b`); only
  `Environment` actually differs from the samconfig values.
- **Review every line of the changeset** (`aws cloudformation describe-change-set
  --change-set-name <name>`). Expected diff (verified by diffing the templates):
  - **9 CREATEs**: `PipelineDlq`, `DlqAlarmTopic`(+policy), `PipelineDlqAlarm`,
    `PipelineDlqEventBridgePolicy`, `SweeperFunction`, `SweeperRole`,
    `VerificationScheduleGroup`, `VerificationSchedulerRole`
  - **12 MODIFYs**: 6 pipeline functions (DLQ env vars, verification timeout),
    3 IAM roles (new `sqs:SendMessage`/`scheduler:CreateSchedule` grants),
    3 EventBridge rules (`DeadLetterConfig` + tightened `RetryPolicy`)
  - **0 DELETEs, 0 REPLACEs, 0 resource renames.**
  - If you see any `Replace: true` or `Delete` action — STOP and investigate.

## 5. Execute and watch

```bash
# exact command SAM printed in step 4, typically:
aws cloudformation execute-change-set \
  --change-set-name <name-sam-printed> --region ap-south-1

# progress / failure reasons:
aws cloudformation describe-stack-events --stack-name llm-incident-response-staging \
  --query 'StackEvents[?contains(ResourceStatus, `FAILED`) || ResourceStatus==`UPDATE_ROLLBACK_IN_PROGRESS`].[LogicalResourceId,ResourceStatusReason]' \
  --output table

aws cloudformation wait stack-update-complete \
  --stack-name llm-incident-response-staging   # returns when done
```

If something fails and a rollback starts: let it finish. The diff is additive, so a
rollback restores today's exact behavior — that is the safety net.

## 6. Post-deploy smoke test

```bash
# 6.1 New resources exist
DLQ_URL=$(aws sqs get-queue-url --queue-name incident-pipeline-dlq-staging --output text)
aws sqs get-queue-attributes --queue-url "$DLQ_URL" \
    --attribute-names ApproximateNumberOfMessages     # expect 0

# 6.2 Pagination fix live (the deployed bug hid new incidents at small limits)
curl -s "https://o212lf1md4.execute-api.ap-south-1.amazonaws.com/Prod/api/incidents?limit=3" \
  | python3 -m json.tool | head -30                   # newest incident must be first

# 6.3 DLQ replay tool finds the new queue (dry run, no side effects)
python scripts/replay_dlq.py --stack llm-incident-response-staging --dry-run

# 6.4 Full pipeline loop — the real end-to-end proof
curl -X POST "https://0l32vjl4n8.execute-api.ap-south-1.amazonaws.com/Prod/demo/inject" \
  -H 'Content-Type: application/json' -d '{"fault_class":"resource_exhaustion"}'
# then poll /api/incidents?limit=3 for ~3 min:
#   new incident appears  -> collector + diagnosis + pagination OK
#   approve it (UI or /demo/approve/{id})
#   status -> executed    -> remediation leg OK
#   verification fills in ~2 min (scheduler-based now, no sleep)
```

## 7. After success: fix samconfig for next time

Add a staging section to `infra/samconfig.toml` so future deploys can't hit the dev
default by accident:

```toml
[staging.deploy.parameters]
stack_name = "llm-incident-response-staging"
s3_bucket = "aws-sam-cli-managed-default-samclisourcebucket-kx2gwyhouegw"
s3_prefix = "llm-incident-response-staging"
region = "ap-south-1"
capabilities = "CAPABILITY_IAM CAPABILITY_NAMED_IAM"
confirm_changeset = false
parameter_overrides = "Environment=\"staging\" ServiceBUrl=\"https://0wv3y5mpal.execute-api.ap-south-1.amazonaws.com/Prod/service-b\" ServiceCUrl=\"https://0wv3y5mpal.execute-api.ap-south-1.amazonaws.com/Prod/service-c\""
```

Then: `sam deploy --config-env staging`.

## 8. Optional cleanup (separate task, needs matching IAM rights)

The zombie dev stack (`llm-incident-response`, `DELETE_FAILED`) still holds:
`ConfigDeliveryChannel`, `IAMPolicyConfigRule`, `PublicS3BucketConfigRule`
(DELETE_FAILED / DELETE_SKIPPED — region-global Config resources), and an S3 bucket
record whose physical bucket no longer exists. To retire it:
`aws cloudformation delete-stack` with the Config resources **retained**, then the
stack can be re-attempted/removed from the console. Harmless to leave, but it is the
reason `sam deploy` with defaults would fail confusingly.
