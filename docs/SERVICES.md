# AWS Services Used by the Project

This document describes the AWS services used by the LLM-Assisted Cloud Incident Response system, when each service is used, and what data it stores or manages.

## End-to-end flow

```text
Demo Lambda services
        ↓
CloudWatch / AWS Config / GuardDuty
        ↓
EventBridge
        ↓
Collector Lambda
        ↓
S3 evidence + DynamoDB incident record
        ↓
Diagnosis Lambda + Amazon Bedrock
        ↓
Slack/dashboard approval
        ↓
Remediation Lambda
        ↓
Verification Lambda
        ↓
DynamoDB verification result
```

## Service summary

| Service | Brief description | When this project uses it | What it stores or manages |
|---|---|---|---|
| **AWS Lambda** | Runs short-lived, event-driven Python functions without managing servers. | All backend stages: demo services, collection, diagnosis, notification, approval, remediation, verification, dashboard, and demo control. | Function code, configuration, environment variables, execution logs, metrics, and temporary execution state. Incident state is stored in DynamoDB, not Lambda. |
| **Amazon API Gateway** | Provides HTTP endpoints that invoke Lambda functions. | Demo service routes, approval links, dashboard APIs, dashboard actions, and demo-control endpoints. | API routes, integrations, request/response configuration, and optionally access logs. It does not store incident records. |
| **Amazon EventBridge** | Routes AWS events to matching targets. | Sends CloudWatch alarm events and GuardDuty findings to `CollectorFunction`. | Event rules, event patterns, targets, and delivery metadata. It is a router, not the system of record. |
| **Amazon CloudWatch** | Provides metrics, logs, alarms, and alarm state. | Detects Lambda duration/errors and service-cascade faults; the Collector and Verification Lambdas query it. | Lambda metrics, application logs, Logs Insights results, alarm definitions, and alarm state. |
| **Amazon S3** | Object storage used as the incident data lake. | Stores collector evidence, runbooks, failed Bedrock responses, and expected evaluation artifacts. | `incidents/<id>/raw_data.json`, `incidents/<id>/llm_raw_response_*.json`, `runbooks/*.md`, and optionally `evaluation/results/summary.json`. |
| **Amazon DynamoDB** | Fast NoSQL storage for structured incident state. | Every incident is created, updated through diagnosis/approval/remediation/verification, and read by the dashboard. | Incident ID, detection metadata, S3 evidence pointer, diagnosis, recommendations, approval state, remediation result, and verification result. |
| **Amazon Bedrock** | Provides foundation models for incident diagnosis. | Diagnosis stage only, after evidence and runbook context are prepared. May be called again for validation-retry or model fallback. | The project does not use Bedrock as persistent storage. Responses are stored in DynamoDB when valid; failed raw responses may be saved to S3. |
| **AWS Config** | Evaluates AWS resources against compliance rules and exposes configuration history. | Detects or investigates misconfiguration incidents, such as public S3 access or permissive IAM policies; Verification re-checks compliance. | Compliance evaluation results, resource configuration history, and configuration items. |
| **Amazon GuardDuty** | Detects suspicious or malicious AWS activity. | GuardDuty findings are routed through EventBridge and collected as security-related `misconfiguration` incidents. | Security findings, finding metadata, severity, affected resources, and activity details. The Collector copies relevant finding data into the incident's S3 evidence bundle. |
| **AWS X-Ray** | Distributed tracing and service dependency visualization. | Collector gathers trace summaries and service-graph information for `service_cascade` incidents. | Trace segments, trace summaries, service maps, latency, errors, faults, and dependency relationships. |
| **AWS IAM** | Controls identities, roles, and permissions. | Supplies execution roles for Lambda; the remediation action `tighten_iam_policy` attaches a predefined restrictive inline policy. | Roles, policies, trust policies, and permissions. The LLM does not generate IAM policy JSON. |
| **AWS Systems Manager Parameter Store** | Stores configuration values and secrets. | Notify and Approval Lambdas read the Slack webhook URL and HMAC approval-token secret. | SecureString parameters such as the Slack webhook and approval secret. |
| **AWS STS** | Provides caller/account identity information. | Used by local health checks and fault-injection utilities to identify the active AWS account. | No project data; returns temporary credentials and caller identity information. |
| **AWS SAM / CloudFormation** | Defines and deploys the infrastructure as code. | Deploys the Lambda functions, IAM roles, S3 bucket, DynamoDB table, EventBridge rules, alarms, and API routes. | CloudFormation stack state, resource definitions, parameters, outputs, and deployment metadata. |

## What each pipeline stage stores

| Pipeline stage | Primary service | Stored result |
|---|---|---|
| Detection | CloudWatch, Config, GuardDuty | Alarm state, compliance result, or security finding |
| Collection | S3 + DynamoDB | Raw evidence bundle in S3 and initial incident record in DynamoDB |
| Diagnosis | Bedrock + DynamoDB | Structured root cause, confidence, reasoning, and recommended actions |
| Notification/approval | SSM + DynamoDB | Slack message delivery and approval/rejection decision |
| Remediation | AWS resource APIs + DynamoDB | Action result: `executed` or `failed` |
| Verification | CloudWatch/Config/S3 + DynamoDB | `resolved`, `not_resolved`, or `inconclusive` with the rechecked signal |
| Dashboard | DynamoDB + S3 | Read-only views of incident records, evidence, runbooks, and analytics |

## Important implementation notes

- **S3 is the raw evidence store; DynamoDB is the incident state store.**
- **Bedrock is not used during remediation or verification.** Verification uses deterministic AWS metrics, alarm state, Config compliance, or S3 public-access settings.
- The main SAM template creates the GuardDuty EventBridge rule, but GuardDuty itself must already be enabled in the AWS account.
- The Collector and Verification Lambdas use AWS Config APIs, but the current template does not create a separate Config recorder/rule set; those resources may be managed externally because an account can have only one active recorder/channel.
- The current notification implementation posts directly to a Slack incoming webhook. Older project descriptions mention SNS, but no SNS topic is provisioned or used by the current backend.

## Main implementation references

- Infrastructure: [`infra/template.yaml`](infra/template.yaml)
- Demo-control infrastructure: [`infra/demo-control-template.yaml`](infra/demo-control-template.yaml)
- End-to-end architecture: [`docs/END_TO_END_ARCHITECTURE.md`](docs/END_TO_END_ARCHITECTURE.md)
- Collector: [`backend/collector/collector_lambda.py`](backend/collector/collector_lambda.py)
- Diagnosis: [`backend/diagnosis/diagnosis_lambda.py`](backend/diagnosis/diagnosis_lambda.py)
- Remediation: [`backend/remediation/remediation_lambda.py`](backend/remediation/remediation_lambda.py) and [`backend/remediation/actions.py`](backend/remediation/actions.py)
- Verification: [`backend/verification/verification_lambda.py`](backend/verification/verification_lambda.py)
