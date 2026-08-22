# Developer Onboarding & Local Environment Setup

- **Space**: Engineering Knowledge Base (`ENG`)
- **Document ID**: `ENG-PAGE-03`
- **Author**: Staff Developer Advocate (rachel.chen@example.com)
- **Last Updated**: 2026-08-20
- **Tags**: `onboarding`, `developer-guide`, `docker`, `local-dev`, `python`, `go`

---

## 1. Welcome to CloudScale Payments Engineering!

This guide walks every newly joined backend engineer through configuring their local workstation, launching the local microservices ecosystem via Docker Compose, seeding mock test data, and executing the automated test suite.

---

## 2. Prerequisites & Software Versions

Ensure you have the following tools installed before beginning setup:

- **macOS / Linux workstation**
- **Git** `>= 2.40`
- **Python** `3.11.x` (managed via `pyenv`)
- **Go** `1.22.x`
- **Docker Desktop** `>= 4.28` (with at least 8 GB RAM and 4 CPUs allocated)
- **Poetry** or standard `pip` + `venv`
- **Pre-commit hooks**: `pre-commit install`

---

## 3. Clone Repository & Setup Virtual Environment

```bash
# Clone the repository
git clone git@github.com:cloudscale-pay/confluence-jira-rag.git
cd confluence-jira-rag

# Create Python 3.11 virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install development dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 4. Spin Up Local Infrastructure with Docker Compose

We provide a comprehensive `docker-compose.yml` containing PostgreSQL 16, Redis 7.2, and Kafka (Redpanda mock):

```bash
# Start all supporting services in background
docker compose up -d postgres redis kafka

# Verify container health status
docker compose ps
```

### 4.1 Apple Silicon (M1/M2/M3) Note

> [!NOTE]
> If you are on an Apple Silicon Mac and experience container architecture mismatch crashes on the `acquirer-mock` container, ensure `DOCKER_DEFAULT_PLATFORM=linux/arm64` is configured in your `~/.zshrc` (refer to `PAY-105` for details).

---

## 5. Seed Test Data & Run Migrations

```bash
# Apply database schema migrations
python -m rag_assistant.db.migrate up

# Seed mock merchant accounts, test cards, and simulated ledgers
python -m rag_assistant.db.seed --environment=local
```

---

## 6. Running Tests & Linters

```bash
# Run unit and integration tests
pytest tests/ -v

# Run type checker and linter
ruff check .
mypy src/
```

---

## 7. Sandbox Test Cards

Use these test cards in local and staging environments:

| Card Brand | Card Number | Expiry | CVV | Expected Result |
| :--- | :--- | :--- | :--- | :--- |
| **Visa (Success)** | `4000 0012 3456 7890` | `12/2028` (MM/YYYY) | `123` | HTTP 200 `AUTHORIZED` |
| **Mastercard (Success)** | `5555 5555 5555 4444` | `08/2027` (MM/YYYY) | `456` | HTTP 200 `AUTHORIZED` |
| **Declined (Insufficient Funds)** | `4000 0012 3456 9999` | `10/2026` (MM/YYYY) | `789` | HTTP 402 `INSUFFICIENT_FUNDS` |
| **Fraud Simulator** | `4000 0012 3456 0001` | `01/2029` (MM/YYYY) | `999` | HTTP 403 `FRAUD_BLOCK` |

> [!WARNING]
> Always pass expiry dates in full `MM/YYYY` format. Passing two-digit year `MM/YY` is currently under bugfix review in `PAY-108`.

---

## 8. Getting Help

- Join the `#dev-onboarding-support` Slack channel.
- Check open tickets tagged `good-first-issue` on Jira project `PAY`.
