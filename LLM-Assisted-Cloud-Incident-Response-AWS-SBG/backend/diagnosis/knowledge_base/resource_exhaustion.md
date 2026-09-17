# Runbook: Resource Exhaustion Incident Response

## 1. Overview
This runbook covers incidents categorized under the `resource_exhaustion` fault class. Resource exhaustion occurs when a compute service (such as AWS Lambda or ECS) experiences memory pressure, execution timeouts, thread pool exhaustion, or high invocation concurrency limits.

## 2. Diagnostic Steps
1. **Analyze CloudWatch Metrics:**
   - Inspect `Duration` metrics over the past 15 minutes. Check if maximum execution time approaches function execution timeout (e.g. > 50,000 ms).
   - Check `Errors` and `Throttles` metric sums to verify if requests are failing due to concurrency limits or runtime exceptions.
2. **Review CloudWatch Logs Insights:**
   - Query `@type = 'REPORT'` log lines to compare `@billedDuration` vs `@duration` and check `@maxMemoryUsed`.
   - Search for `Memory limit exceeded`, `Task timed out`, or `OutOfMemoryError` in error traces.
3. **Isolate Affected Component:**
   - Confirm whether the issue is isolated to a single Lambda function (e.g. Service A) or widespread across the environment.

## 3. Recommended Remediation Actions
- **`scale_up`**: If memory usage exceeds 85% of allocated memory or duration spikes under heavy payload/concurrency without downstream errors, increase function memory allocation or provisioned concurrency.
- **`restart_service`**: If memory usage continuously increases over consecutive invocations (indicating an in-memory leak or hanging thread pool), force a service container/environment restart to clear transient state.
- **`manual_review_required`**: If duration is high due to unexpected database lock contention or third-party external API slowness, flag for manual engineering review.
