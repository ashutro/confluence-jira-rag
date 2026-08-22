# Incident Response Runbook: Payment Webhook 504 Gateway Timeouts

- **Space**: Engineering Knowledge Base (`ENG`)
- **Document ID**: `ENG-PAGE-02`
- **Author**: SRE Team Lead (sam.patel@example.com)
- **Last Updated**: 2026-08-18
- **Tags**: `runbook`, `incident-response`, `webhooks`, `sre`, `troubleshooting`, `sev-2`

---

## 1. Overview & Alert Trigger Conditions

This runbook guides on-call engineers responding to **Alert: `WebhookDeliveryLatencyHigh`** or **Alert: `WebhookWorkerErrorRate5xx`**.

- **Severity Level**: SEV-2 (SEV-1 if merchant error rate > 5% for > 10 minutes)
- **Alert Channel**: `#oncall-payments-alerts` on Slack / PagerDuty Escalation Policy `Core-SRE`
- **Target SLA**: Initial triage within 5 minutes; mitigation within 20 minutes.

---

## 2. Common Symptoms

1. Datadog dashboard shows `pay-webhook` p99 delivery latency spiking above 5,000ms.
2. Merchants report delayed payment confirmation events (`payment.captured`, `payment.failed`).
3. Redis worker queue `queue:webhooks:dispatch` backlog depth grows continuously (> 50,000 pending items).
4. Outbound HTTP requests from `pay-webhook` return HTTP 504 Gateway Timeout or HTTP 502 Bad Gateway.

---

## 3. Step-by-Step Triage & Diagnosis Procedure

### Step 3.1: Check Pod Health and Worker Pool Metrics

Run the following kubectl commands in the payment production cluster:

```bash
# Check running webhook pods
kubectl get pods -n payments -l app=pay-webhook

# Check pod resource utilization
kubectl top pods -n payments -l app=pay-webhook

# View real-time error logs filtering for 504 errors
kubectl logs -n payments -l app=pay-webhook --tail=100 -f | grep -i "504 Gateway Timeout"
```

### Step 3.2: Inspect Redis Queue Backlog

Connect to the Redis read-replica to evaluate queue depth without loading the primary master:

```bash
# Get total pending webhook tasks
redis-cli -h redis-readonly.internal.pay LLEN queue:webhooks:dispatch

# Get dead-letter queue (DLQ) count
redis-cli -h redis-readonly.internal.pay LLEN queue:webhooks:dlq
```

### Step 3.3: Identify Slow or Failing Destination Merchants

Run the diagnostic query on Athena or check Datadog facet `merchant_domain`:

```sql
SELECT merchant_id, merchant_domain, count(*), avg(duration_ms)
FROM webhook_logs
WHERE timestamp > NOW() - INTERVAL '15 MINUTE'
  AND status_code IN (502, 504)
GROUP BY merchant_id, merchant_domain
ORDER BY count(*) DESC
LIMIT 10;
```

---

## 4. Mitigation Actions

### Action A: Scale Out the Webhook Worker Deployment (Horizontal Pod Autoscaler)

If CPU or queue depth is the primary bottleneck and downstream merchant endpoints are healthy:

```bash
kubectl scale deployment pay-webhook -n payments --replicas=30
```

### Action B: Quarantine Unresponsive Merchant Endpoints (Circuit Breaker)

If a single high-volume merchant endpoint is stalling connection worker threads:

1. Enable the circuit breaker for that merchant ID via Consul Key-Value:
   ```bash
   consul kv put config/pay-webhook/quarantine_merchants/merchant_xyz123 true
   ```
2. This diverts traffic for `merchant_xyz123` into the deferred low-priority queue `queue:webhooks:deferred`, freeing primary workers.

### Action C: Restart Hanging Worker Pods Gracefully

If workers suffer memory leak or socket exhaustion (as documented in `PAY-102`):

```bash
kubectl rollout restart deployment pay-webhook -n payments
```

---

## 5. Escalation Path

| Escalation Level | Role | Contact Point |
| :--- | :--- | :--- |
| **Primary (L1)** | On-Call SRE Engineer | PagerDuty Schedule `Payments-OnCall-L1` |
| **Secondary (L2)** | Webhook Platform Tech Lead | Slack `@lead-webhook-eng` |
| **Incident Commander** | VP of Infrastructure | `#incident-commander` |

---

## 6. Post-Incident Requirements

1. File a Jira postmortem issue under project `PAY` with issue type `Incident`.
2. Schedule a blameless postmortem meeting within 48 business hours.
3. Reference `PAY-102` and `PAY-103` for related known issues.
