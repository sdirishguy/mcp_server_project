# MCP Server Project

A production-ready Model Context Protocol (MCP) server for secure, programmable agent tools over HTTP, built with **Python 3.12+**, **Starlette**, and **FastMCP**.

Ideal for orchestrating local/remote AI agent workflows, automating filesystem & shell operations, and integrating with LLM APIs.

---

## ✨ Highlights

- **New audit logging API**: `AuditEventType` + `AuditLogger.log_event(...)`
- **Auth**: JWT (preferred) or local provider, with RBAC scaffolding
- **Rate limiting** on auth endpoints (SlowAPI), disabled in tests
- **Security headers** (incl. HSTS), CORS, sandboxed filesystem
- **Monitoring**: `/health`, `/metrics` (Prometheus), structured logs
- **CI**: Ruff + Mypy + Pytest matrix (3.12/3.13), caching & concurrency
- **Pre-commit** with Ruff (format + lint)

**Test status**: 53 passing, 21 intentionally skipped (FastMCP lifespan tests; see `FASTMCP_LIFESPAN_ISSUE_REPORT.md`)

---

## 📁 Project Structure

```
mcp_server_project/
├── app/
│   ├── main.py              # ASGI app, routes, middleware, lifespan
│   ├── tools.py             # Tool handlers
│   ├── settings.py          # Pydantic settings
│   ├── monitoring.py        # Prometheus & structured logging
│   └── mcp/
│       ├── adapters/        # REST API, PostgreSQL
│       ├── cache/           # In-memory cache
│       ├── core/            # Adapter manager
│       └── security/        # AuthN/Z, audit logging
├── tests/                   # Test suite
├── shared_host_folder/      # Sandboxed working directory
├── logs/                    # App & audit logs (gitignored)
├── host_data/               # Persistent data
├── Dockerfile
├── docker-compose.yml
├── DOCKER.md
├── requirements.txt
├── pyproject.toml
├── .pre-commit-config.yaml
├── FASTMCP_LIFESPAN_ISSUE_REPORT.md
├── PRODUCTION_READINESS_REPORT.md
└── README.md
```

---

## 📦 Requirements

- Python **3.12+** (3.13 supported)
- pip
- (Optional) Docker & Docker Compose
- Dependencies: see `requirements.txt` / `pyproject.toml`

---

## ⚙️ Installation (local)

```bash
git clone https://github.com/sdirishguy/mcp_server_project.git
cd mcp_server_project

python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

**Environment (recommended):**
```bash
# Copy the example and customize:
cp .env.example .env

# Or set manually:
export MCP_SERVER_PORT=8000
export AUDIT_LOG_FILE=./logs/audit.log
export JWT_SECRET="change-this-in-prod"
# Optional for tools:
export OPENAI_API_KEY=...
export GEMINI_API_KEY=...
```

**Run:**
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Health:**
```bash
curl http://localhost:8000/health
```

---

## 🐳 Docker

**Docker Compose (recommended):**
```bash
docker-compose up -d
curl http://localhost:8000/health
```

**Docker CLI:**
```bash
docker build -t mcp-server .
docker run -d \
  --name mcp-server \
  -p 8000:8000 \
  -e MCP_SERVER_PORT=8000 \
  -e AUDIT_LOG_FILE=/app/logs/audit.log \
  -e JWT_SECRET="change-this-in-prod" \
  -v "$(pwd)/host_data:/app/host_data" \
  -v "$(pwd)/logs:/app/logs" \
  -v "$(pwd)/shared_host_folder:/app/shared_host_folder" \
  mcp-server
```

**Details:** see `DOCKER.md`.

---

## 🔐 Authentication

Default provider: JWT (if `JWT_SECRET` is non-default); otherwise local.

**Get token:**
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

---

## 🧰 Tools (examples)

**Filesystem:**
- `file_system_create_directory`
- `file_system_write_file`
- `file_system_read_file`
- `file_system_list_directory`

**Shell:**
- `execute_shell_command` (allowlist/disabled via env)

**Code generation:**
- `llm_generate_code_openai`
- `llm_generate_code_gemini`
- `llm_generate_code_local` (placeholder)

**Call a tool:**
```bash
TOKEN=... # from login
curl -X POST http://localhost:8000/mcp/mcp.json/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"file_system_create_directory","arguments":{"path":"tmp/newdir"}},"id":1}'
```

---

## 📝 API Endpoints

- `GET /health` – health check
- `GET /metrics` – Prometheus metrics
- `GET /whoami` – server/providers info
- `POST /api/auth/login` – obtain token
- `POST /api/adapters/{adapter_type}` – create adapter
- `POST /api/adapters/{instance_id}/execute` – execute adapter request
- `POST /mcp/mcp.json/` – JSON-RPC for tool calls (requires auth)

---

## 🧾 Audit logging (new API)

**Success:**
```python
await audit_logger.log_event(
    AuditEventType.LOGIN,
    actor=user_id,  # or username
    context={"success": True, "ip": request.client.host},
)
```

**Failure:**
```python
await audit_logger.log_event(
    AuditEventType.LOGIN,
    actor=username,
    context={"success": False, "reason": "invalid_credentials"},
)
```

**Legacy API/shims were removed in v0.1.0.**

---

## ✅ Testing

**Local:**
```bash
pytest -q
```

**Common flags:**
```bash
export ANYIO_BACKEND=asyncio
pytest -q
```

**Status:** 53 passing, 21 skipped (FastMCP lifespan-dependent). See `FASTMCP_LIFESPAN_ISSUE_REPORT.md`.

**Lint & types:**
```bash
ruff check . && ruff format --check .
mypy .
```

---

## 🧑‍💻 Dev workflow

```bash
pip install pre-commit
pre-commit install
# optional one-shot on entire repo:
pre-commit run --all-files
```

---

## 🔒 Security notes

- Set non-default `JWT_SECRET` in prod/CI.
- App sends strict security headers (incl. HSTS); terminate TLS at the proxy/load balancer.
- Filesystem operations are sandboxed to `shared_host_folder`.

---

## 📚 More docs

- `DOCKER.md` – Docker usage
- `FASTMCP_LIFESPAN_ISSUE_REPORT.md` – why 21 tests are skipped & the plan
- `PRODUCTION_READINESS_REPORT.md` – current posture & checklist

---

## 📝 License

MIT
