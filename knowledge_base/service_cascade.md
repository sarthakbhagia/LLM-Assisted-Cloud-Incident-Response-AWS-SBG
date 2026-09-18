# Runbook: Multi-Service Cascade Incident Response

## 1. Overview
This runbook covers incidents categorized under the `service_cascade` fault class. Cascading failures occur when a downstream microservice (e.g. Service C) experiences latency spikes or internal errors, causing upstream callers (Service B -> Service A) to exhaust connection pools, hit timeouts, or propagate errors across the service graph.

## 2. Diagnostic Steps
1. **Analyze X-Ray Service Graph & Trace Summaries:**
   - Examine response time distribution and fault/error flags across `ServiceA`, `ServiceB`, and `ServiceC`.
   - Identify the origin root-cause node in the dependency graph where high latency (> 1,000 ms) or initial errors first originated.
2. **Correlate Cross-Service Log Groups:**
   - Execute CloudWatch Logs Insights across `/aws/lambda/ServiceA`, `/aws/lambda/ServiceB`, and `/aws/lambda/ServiceC`.
   - Trace `@requestId` or correlated error messages (`downstream_request_failed`, `HTTP error`, `Timeout`).
3. **Determine Dependency Topology:**
   - Confirm whether upstream failure in Service A was directly triggered by downstream unresponsiveness in Service C or B.

## 3. Recommended Remediation Actions
- **`restart_downstream_service`**: If the root leaf dependency (Service C or Service B) is stuck in a deadlocked state, high latency loop, or unhandled exception state causing upstream cascade failures, restart the downstream service instance to restore normal response latency.
- **`restart_service`**: If the primary entrypoint service (Service A) connection pool is exhausted and failing to recover after downstream recovery, restart Service A.
- **`manual_review_required`**: If the cascade is caused by database resource locks or circuit-breaker misconfiguration requiring multi-service code patches, escalate for manual engineering review.
