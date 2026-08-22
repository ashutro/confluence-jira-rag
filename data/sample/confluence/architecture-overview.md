# Architecture Overview & Service Topology

- **Space**: Engineering Knowledge Base (`ENG`)
- **Document ID**: `ENG-PAGE-01`
- **Author**: Staff Architect (alex.morgan@example.com)
- **Last Updated**: 2026-08-15
- **Tags**: `architecture`, `microservices`, `topology`, `redis`, `kafka`, `core-platform`

---

## 1. Executive Summary

The CloudScale Payments Platform is a distributed event-driven payment processing infrastructure designed for high-throughput, sub-100ms authorization latencies, and 99.999% availability. This document details the core service topology, communication protocols, datastores, and failure isolation domains.

---

## 2. Core Service Topology

```text
[ Client Application / Checkout SDK ]
                 |
                 v
       [ API Gateway (Kong) ]
         |                 |
    (Auth / Rate Limit)    | (TLS Termination)
         |                 |
         v                 v
  [ Payment Ingestion API (Go) ] <-----> [ Redis Cluster (Cache & Idempotency) ]
         |
    (Kafka Topic: `payments.inbound.v1`)
         |
         v
  [ Payment Settlement Engine (Python / FastAPI) ]
         |
    +----+-----------------------+-----------------------+
    |                            |                       |
    v                            v                       v
[ Ledger DB (PostgreSQL) ] [ Fraud Detection Svc ] [ External Acquirer Gateways ]
                                                         |
                                                         v
                                              [ Webhook Dispatcher (Go) ]
```

### 2.1 Services Breakdown

1. **API Gateway (Kong)**:
   - Terminates TLS, validates JWT bearer tokens, and applies Tiered Rate Limiting middleware via Redis.
   - Enforces IP whitelisting for enterprise webhook callbacks.

2. **Payment Ingestion Service (`pay-ingest`)**:
   - High-performance Go service accepting incoming payment intent requests.
   - Enforces payload schema validation and idempotency key checks stored in Redis with 24-hour TTL.
   - Publishes valid payment intents to Kafka topic `payments.inbound.v1`.

3. **Payment Settlement Engine (`pay-settle`)**:
   - Python 3.11 service handling transaction orchestration, multi-currency conversion, and state transitions (`INITIATED`, `AUTHORIZED`, `CAPTURED`, `SETTLED`, `FAILED`).
   - Interacts with Acquirer APIs (Stripe, Adyen, Chase) via async connection pools.

4. **Ledger Service (`pay-ledger`)**:
   - Source-of-truth double-entry bookkeeping datastore built on PostgreSQL with partitioned transactional tables.
   - Enforces strict ACID compliance with row-level locking on account balances.

5. **Webhook Dispatcher (`pay-webhook`)**:
   - Asynchronous worker pool that delivers signed HMAC-SHA256 event notifications to merchant callback URLs.
   - Implements exponential backoff retry policy (1m, 5m, 15m, 1h, 6h).

---

## 3. Data Storage & Persistence Layers

| Component | Technology | Primary Use Case | Retention / Backup |
| :--- | :--- | :--- | :--- |
| **Primary Ledger** | PostgreSQL 16 (RDS Multi-AZ) | Double-entry accounts, balances, transactions | Continuous WAL archiving + 30-day snapshot |
| **Idempotency & Cache** | Redis 7.2 Cluster (ElastiCache) | Idempotency keys, session state, rate limit tokens | 24-hour TTL, in-memory with AOF persistence |
| **Message Streaming** | Apache Kafka (MSK) | Asynchronous decoupled transaction pipelines | 7-day retention on partitioned topics |
| **Audit & Cold Logs** | AWS S3 + Athena | Raw event streams, JSON audit payloads | 7-year immutable compliance archive |

---

## 4. Key Architectural Decisions (ADRs)

- **ADR-001 (Idempotency)**: Every payment mutation endpoint requires an `Idempotency-Key` header. Requests with duplicate keys return the cached HTTP response without re-executing settlement.
- **ADR-004 (Event Sourcing for Ledgers)**: Account balance mutations cannot be updated directly; all mutations must be posted as debit/credit entry pairs in the `ledger_entries` table.
- **ADR-007 (Rate Limiting)**: Redis Token Bucket implementation with fallback to local memory in case of Redis cluster partition.

---

## 5. Related Jira Epics and Tickets

- `PAY-101`: Next-Gen Webhook Reliability & Idempotency Pipeline
- `PAY-104`: Implement Tiered Rate Limiting middleware with Redis Token Bucket
- `PAY-106`: SEV-2 Postmortem: Database connection pool starvation during Black Friday traffic spike
