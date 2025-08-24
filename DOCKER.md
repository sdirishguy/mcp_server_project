# Docker Setup for MCP Server

This guide shows how to run the MCP Server in containers with sane defaults.

## Quick Start (Compose)

```bash
docker-compose up -d
curl http://localhost:8000/health
docker-compose down
```

## Docker CLI

**Build:**
```bash
docker build -t mcp-server .
```

**Run:**
```bash
docker run -d \
  --name mcp-server \
  -p 8000:8000 \
  -e MCP_SERVER_PORT=8000 \
  -e AUDIT_LOG_FILE=/app/logs/audit.log \
  -e JWT_SECRET="change-this-in-prod" \
  -e ENVIRONMENT=development \
  -v "$(pwd)/host_data:/app/host_data" \
  -v "$(pwd)/logs:/app/logs" \
  -v "$(pwd)/shared_host_folder:/app/shared_host_folder" \
  mcp-server
```

## Configuration

### Environment variables

- `MCP_SERVER_PORT` – server port (default 8000)
- `MCP_BASE_WORKING_DIR` – sandbox base dir (default `./shared_host_folder`)
- `AUDIT_LOG_FILE` – path to audit log file
- `ENVIRONMENT` – development / staging / production
- `ALLOW_ARBITRARY_SHELL_COMMANDS` – true|false (default: disabled)
- `JWT_SECRET` – required for JWT auth in prod/non-test
- `OPENAI_API_KEY`, `GEMINI_API_KEY` – for LLM tools

### Volumes

- `./host_data:/app/host_data` – persistent app data
- `./logs:/app/logs` – logs & audit log
- `./shared_host_folder:/app/shared_host_folder` – sandboxed working dir

Ensure these host dirs are writable by the container user.

## Endpoints

- `GET /health` – health check
- `GET /whoami` – server/providers info
- `POST /api/auth/login` – login
- `POST /api/adapters/{type}` – create adapters
- `POST /api/adapters/{id}/execute` – execute
- `POST /mcp/mcp.json/` – MCP JSON-RPC (auth required)

## Default credentials (dev only)

- `admin` / `admin123`

Change via env or secrets in production.

## Troubleshooting

**Permissions:** `chmod -R a+rw logs host_data shared_host_folder`

**Port conflicts:** change `-p 8000:8000`

**Logs:** `docker logs mcp-server`

**Shell:** `docker exec -it mcp-server /bin/bash`
