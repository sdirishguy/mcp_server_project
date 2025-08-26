# MCP Server Project

A secure Model Context Protocol (MCP) server providing HTTP endpoints for AI agent tool execution. Built with Python 3.12+, Starlette, and FastMCP.

## Quick Start

```bash
# Clone and setup
git clone https://github.com/sdirishguy/mcp_server_project.git
cd mcp_server_project
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Test
curl http://localhost:8000/health
```

## Docker

```bash
docker-compose up -d
curl http://localhost:8000/health
```

## Configuration

Required environment variables:
```bash
JWT_SECRET="your-secret-key-32-chars-minimum"    # Required for production
ADMIN_USERNAME="admin"                            # Default admin user
ADMIN_PASSWORD="secure-password"                  # Change from default
```

Optional configuration:
```bash
SERVER_PORT=8000
MCP_BASE_WORKING_DIR="./shared_host_folder"
ENVIRONMENT="development"                         # development|staging|production
ALLOW_ARBITRARY_SHELL_COMMANDS="false"           # Security: disabled by default
CORS_ORIGINS="http://localhost:3000,https://yourdomain.com"

# API Keys for LLM tools
OPENAI_API_KEY="sk-..."
GEMINI_API_KEY="..."
```

## Authentication

Get a token:
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

Use token:
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8000/api/protected
```

## Available Tools

| Tool | Description |
|------|-------------|
| `file_system_create_directory` | Create directories (sandboxed) |
| `file_system_write_file` | Write text files |
| `file_system_read_file` | Read text files |
| `file_system_list_directory` | List directory contents |
| `execute_shell_command` | Execute shell commands (filtered) |
| `llm_generate_code_openai` | Generate code via OpenAI API |
| `llm_generate_code_gemini` | Generate code via Gemini API |

## API Endpoints

- `GET /health` - Health check
- `GET /metrics` - Prometheus metrics  
- `POST /api/auth/login` - Authentication
- `POST /mcp/mcp.json/` - MCP JSON-RPC (requires auth)
- `POST /api/adapters/{type}` - Create data adapters
- `GET /docs` - Interactive API documentation

## Security Features

- JWT-based authentication with configurable providers
- Path traversal prevention for file operations  
- Shell command filtering and sandboxing
- Rate limiting on authentication endpoints
- Security headers (HSTS, CSP, etc.)
- CORS configuration
- Audit logging for all operations

## Development

Run tests:
```bash
pytest -q  # 53 passing, 21 skipped (FastMCP lifespan issue)
```

## Testing

Run tests: `pytest -q` (53 passing, 21 skipped due to FastMCP lifespan integration)

The skipped tests require proper ASGI lifespan management which TestClient doesn't provide by default. Production server works correctly.

Linting:
```bash
pre-commit install
pre-commit run --all-files
```

## Production Deployment

1. Set strong `JWT_SECRET` (32+ characters)
2. Change default `ADMIN_PASSWORD` 
3. Set `ENVIRONMENT=production`
4. Configure appropriate `CORS_ORIGINS`
5. Use HTTPS termination at load balancer
6. Monitor `/health` and `/metrics` endpoints

See `PRODUCTION_READINESS_REPORT.md` for detailed checklist.

## Architecture

- **FastMCP**: Tool execution via Model Context Protocol
- **Starlette**: Async web framework with middleware
- **Pydantic**: Configuration management and validation
- **Prometheus**: Metrics collection
- **JWT**: Stateless authentication 
- **Audit Logging**: Structured event logging

## License

MIT