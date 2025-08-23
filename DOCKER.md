# Docker Setup for MCP Server

This document explains how to run the MCP Server in a Docker container.

## Quick Start

### Using Docker Compose (Recommended)

1. **Build and run the container:**
   ```bash
   docker-compose up -d
   ```

2. **Check if the server is running:**
   ```bash
   curl http://localhost:8000/health
   ```

3. **Stop the container:**
   ```bash
   docker-compose down
   ```

### Using Docker directly

1. **Build the image:**
   ```bash
   docker build -t mcp-server .
   ```

2. **Run the container:**
   ```bash
   docker run -d \
     --name mcp-server \
     -p 8000:8000 \
     -v $(pwd)/host_data:/app/host_data \
     -v $(pwd)/logs:/app/logs \
     -v $(pwd)/shared_host_folder:/app/shared_host_folder \
     -e MCP_SERVER_PORT=8000 \
     -e AUDIT_LOG_FILE=/app/logs/audit.log \
     -e ENVIRONMENT=development \
     mcp-server
   ```

## Configuration

### Environment Variables

- `MCP_SERVER_PORT`: Port for the server (default: 8000)
- `MCP_BASE_WORKING_DIR`: Base working directory for sandboxed operations
- `AUDIT_LOG_FILE`: Path to audit log file
- `ENVIRONMENT`: Environment mode (development/staging/production)
- `ALLOW_ARBITRARY_SHELL_COMMANDS`: Enable/disable shell command execution
- `OPENAI_API_KEY`: OpenAI API key for code generation
- `GEMINI_API_KEY`: Google Gemini API key for code generation

### Volumes

- `./host_data:/app/host_data`: Persistent data storage
- `./logs:/app/logs`: Log files
- `./shared_host_folder:/app/shared_host_folder`: Shared working directory

## API Endpoints

- `GET /health`: Health check
- `GET /whoami`: Server info
- `POST /api/auth/login`: Authentication
- `POST /api/adapters/{type}`: Create adapters
- `POST /api/adapters/{id}/execute`: Execute adapter requests
- `GET /mcp/mcp.json/`: MCP tools specification (requires auth)

## Authentication

Default credentials:
- Username: `admin`
- Password: `admin123`

Example login:
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

## Available Tools

The MCP server provides the following tools:

1. **File System Operations:**
   - `file_system_create_directory`: Create directories
   - `file_system_write_file`: Write files
   - `file_system_read_file`: Read files
   - `file_system_list_directory`: List directory contents

2. **Shell Commands:**
   - `execute_shell_command`: Execute shell commands (if enabled)

3. **Code Generation:**
   - `llm_generate_code_openai`: Generate code using OpenAI
   - `llm_generate_code_gemini`: Generate code using Google Gemini
   - `llm_generate_code_local`: Local LLM code generation (placeholder)

## Security Features

- Non-root user execution
- Sandboxed file system operations
- Configurable shell command allowlist
- Audit logging
- Authentication and authorization
- CORS configuration

## Troubleshooting

### Check container logs:
```bash
docker logs mcp-server
```

### Check container status:
```bash
docker ps -a
```

### Access container shell:
```bash
docker exec -it mcp-server /bin/bash
```

### Common Issues

1. **Permission denied errors**: Ensure volume directories have proper permissions
2. **Port already in use**: Change the port mapping in docker-compose.yml
3. **API key errors**: Set the required environment variables for LLM tools
