# API Rate Limiting & Tiered Throttling Policy

- **Space**: Engineering Knowledge Base (`ENG`)
- **Document ID**: `ENG-PAGE-04`
- **Author**: Principal Security & API Architect (marcus.vance@example.com)
- **Last Updated**: 2026-08-10
- **Tags**: `rate-limiting`, `api-policy`, `throttling`, `redis`, `security`, `kong`

---

## 1. Purpose & Scope

To protect the CloudScale Payments API from DDoS attacks, rogue merchant integrations, and noisy neighbors, all public inbound endpoints enforce strict tiered rate limiting.

---

## 2. Rate Limit Tiers

Rate limits are calculated on a rolling 60-second window per API Key and Merchant Organization ID:

| Tier Name | Requests / Second (RPS) | Burst Limit (Token Bucket Capacity) | Monthly Quota | Use Case |
| :--- | :--- | :--- | :--- | :--- |
| **Sandbox / Starter** | 20 RPS | 40 requests | 250,000 reqs/mo | Local testing & free-tier merchants |
| **Growth** | 100 RPS | 200 requests | 2,500,000 reqs/mo | Mid-market merchants |
| **Enterprise** | 500 RPS | 1,000 requests | Unlimited | High-volume merchants & marketplace platforms |
| **Internal Microservices** | 2,000 RPS | 5,000 requests | Unlimited | Service-to-service mTLS mesh |

---

## 3. Rate Limit Response Headers

Every API response from the Kong API Gateway includes standard IETF-compliant rate limiting headers:

```http
HTTP/1.1 200 OK
Content-Type: application/json
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 84
X-RateLimit-Reset: 1724339400
Retry-After: 0
```

When a merchant exceeds their quota, the gateway immediately returns `HTTP 429 Too Many Requests`:

```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "You have exceeded your API request quota of 100 requests/sec. Please retry after 12 seconds.",
    "retry_after_seconds": 12,
    "tier": "GROWTH",
    "doc_url": "https://docs.cloudscale.pay/errors/rate-limiting"
  }
}
```

---

## 4. Technical Implementation: Redis Token Bucket

- Implemented in Lua within Redis (`rate_limit_token_bucket.lua`) for atomic decrement and timestamp refresh.
- Redis key naming pattern: `ratelimit:{merchant_id}:{window_epoch_minute}` with 120-second TTL.
- Fallback behavior: If Redis is unreachable, the API Gateway degrades gracefully into local in-memory token buckets with a 20% reduced burst allowance (refer to `PAY-104`).

---

## 5. Requesting Rate Limit Upgrades or Temporary Exemptions

Merchants preparing for flash sales (e.g., Cyber Monday) can request a temporary limit increase:

1. Account Executive submits a Jira ticket under project `PAY` using template `Rate Limit Exemption Request`.
2. SRE team reviews database capacity and provisions dynamic overrides in Consul KV:
   ```bash
   consul kv put config/ratelimits/overrides/merchant_enterprise_999 '{"rps": 1500, "expires_at": "2026-12-01T00:00:00Z"}'
   ```
3. Overrides take effect within 30 seconds without restarting services.
