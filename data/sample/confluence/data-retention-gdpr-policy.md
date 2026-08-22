# Data Retention & GDPR/PCI-DSS Compliance Policy

- **Space**: Engineering Knowledge Base (`ENG`)
- **Document ID**: `ENG-PAGE-05`
- **Author**: Lead Compliance & Data Governance Officer (elena.rostova@example.com)
- **Last Updated**: 2026-08-12
- **Tags**: `compliance`, `gdpr`, `pci-dss`, `data-retention`, `pii`, `security`

---

## 1. Overview & Regulatory Mandate

As a PCI-DSS Level 1 service provider and processor of European customer transactions under GDPR, CloudScale Payments enforces strict lifecycle policies regarding data classification, field-level encryption, masking, and automated data purging.

---

## 2. Data Classification Matrix

| Data Classification | Examples | Storage Location | Retention Period | Deletion / Purge Method |
| :--- | :--- | :--- | :--- | :--- |
| **Cardholder Data (CHD)** | Primary Account Number (PAN), CVV | Encrypted Token Vault (HSM) | 0 seconds for CVV (never stored post-auth); PAN tokenized | HSM master key rotation |
| **Personally Identifiable (PII)** | Customer email, billing address, phone, IP | PostgreSQL `customers` table | 90 days after account closure | Pseudonymized via hash + salt |
| **Transaction Records** | Amounts, currency, status, merchant ID | PostgreSQL `ledger_entries` | 7 years (Statutory tax requirement) | Immutable archive to S3 Glacier |
| **Raw Request / Debug Logs** | API request headers, payload dumps | CloudWatch / Datadog / S3 | 30 days maximum | S3 Lifecycle expiration rule |

---

## 3. PII Masking and Anonymization Standards

1. **Card Numbers**: Must always be masked as `****-****-****-1234` (first 6 and last 4 digits only).
2. **Customer Names & Emails in Logs**: Must be redacted via regex filters before emitting log events:
   ```json
   {
     "customer_id": "cust_88231",
     "email": "j***e@domain.com",
     "ip_address": "192.168.***.***"
   }
   ```
3. **GDPR Right to Be Forgotten (Erasure Requests)**:
   - When a deletion webhook (`customer.erasure_requested`) is received, the automated cron job flags customer records and overwrites PII fields with cryptographically random tokens within 72 hours.
   - Financial ledger entries are retained with anonymized customer IDs to satisfy financial auditing laws.
   - Work is currently tracked under Jira issue `PAY-107`.

---

## 4. Compliance Audits & Verification

- Annual PCI-DSS audit: Q3 every year.
- S3 Bucket Lifecycle verification script: Runs weekly via AWS Lambda `audit-s3-retention-rules`.
- Any security or compliance violation must be escalated immediately to `#security-incident` and logged under Jira project `PAY` with security flag.
