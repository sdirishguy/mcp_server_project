# MCP Server Project

A **Model Context Protocol (MCP) Server** for secure, programmable agent tools over HTTP, built with Python 3.12, FastMCP, and Starlette/FastAPI.

Ideal for orchestrating local or remote AI agent workflows, automating file and shell operations, and integrating with LLM APIs.

---

## 🚀 Overview

This server exposes modular tools—filesystem, shell, and LLM code generation—via JSON-RPC over HTTP with robust sandboxing and modern ASGI architecture.

**Deploy anywhere**: local dev, cloud, or container, and easily plug in new tools as your agents grow.

---

## 🗂️ Project Structure

```
mcp_server_project/
├── app/
│   ├── main.py              # Entry point (ASGI app, tool registration)
│   ├── tools.py             # All tool handlers
│   ├── config.py            # Env/config management
│   └── mcp/                 # MCP core components
│       ├── adapters/        # REST API, PostgreSQL adapters
│       ├── cache/           # Memory cache implementation
│       ├── core/            # Adapter management
│       └── security/        # Auth, audit logging
├── tests/                   # Test suite
├── shared_host_folder/      # Sandboxed working directory
├── logs/                    # Audit and application logs
├── host_data/               # Persistent data storage
├── Dockerfile               # Container configuration
├── docker-compose.yml       # Docker Compose setup
├── DOCKER.md                # Docker documentation
├── test_docker.sh           # Docker testing script
├── requirements.txt         # Python dependencies
├── pyproject.toml           # Project configuration
├── .flake8                  # Code formatting rules
└── README.md
```

## 📦 Requirements

### Software

- **Python 3.12+** (Tested on 3.12.3)
- **pip** (Python package manager)
- **Docker** *(optional, for container deployment)*
- **Git** (for cloning repo)

### Python Libraries

All dependencies are specified in `requirements.txt`:

- **fastmcp==2.8.0** - MCP server framework
- **starlette==0.47.0** - ASGI framework
- **uvicorn==0.34.3** - ASGI server
- **httpx==0.28.1** - HTTP client
- **pydantic==2.11.5** - Data validation
- **openai==1.84.0** - OpenAI API integration
- **google-generativeai==0.8.5** - Google Gemini API integration
- **python-dotenv==1.1.0** - Environment variable management

---

## 🛠️ Installation & Setup

### Option 1: Local Development

**1. Clone the repo:**
```bash
git clone https://github.com/SDIRISHGUY/MCP_SERVER_PROJECT.git
cd MCP_SERVER_PROJECT
```

**2. Set up a Python virtual environment:**
```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

**3. Install dependencies:**
```bash
pip install -r requirements.txt
```

**4. Set environment variables (optional):**
```bash
export OPENAI_API_KEY=sk-...
export GEMINI_API_KEY=...
export MCP_SERVER_PORT=8000
export AUDIT_LOG_FILE=./logs/audit.log
```

**5. Start the server:**
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Option 2: Docker Deployment (Recommended)

**1. Using Docker Compose (easiest):**
```bash
# Build and start the container
docker-compose up -d

# Check if it's running
curl http://localhost:8000/health

# Run automated tests
./test_docker.sh
```

**2. Using Docker directly:**
```bash
# Build the image
docker build -t mcp-server .

# Run the container
docker run -d \
  --name mcp-server \
  -p 8000:8000 \
  -v $(pwd)/host_data:/app/host_data \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/shared_host_folder:/app/shared_host_folder \
  mcp-server
```

For detailed Docker instructions, see [DOCKER.md](DOCKER.md).

---

## 🔧 Available Tools

The MCP Server provides **8 tools** for agent operations:

### File System Operations
- **`file_system_create_directory`** - Create directories within sandbox
- **`file_system_write_file`** - Write text content to files
- **`file_system_read_file`** - Read text content from files
- **`file_system_list_directory`** - List directory contents

### Shell Commands
- **`execute_shell_command`** - Execute shell commands (configurable allowlist)

### Code Generation
- **`llm_generate_code_openai`** - Generate code using OpenAI API
- **`llm_generate_code_gemini`** - Generate code using Google Gemini API
- **`llm_generate_code_local`** - Local LLM code generation (placeholder)

---

## 🧪 Example Tool Calls

### Authentication
```bash
# Login to get authentication token
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

### File System Operations
```bash
# Create directory
curl -X POST http://localhost:8000/mcp/mcp.json/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"file_system_create_directory","arguments":{"path":"tmp/newdir"}},"id":1}'

# Write file
curl -X POST http://localhost:8000/mcp/mcp.json/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"file_system_write_file","arguments":{"path":"tmp/newdir/hello.txt","content":"Hello, world!"}},"id":2}'

# Read file
curl -X POST http://localhost:8000/mcp/mcp.json/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"file_system_read_file","arguments":{"path":"tmp/newdir/hello.txt"}},"id":3}'
```

### Shell Commands
```bash
# Execute shell command
curl -X POST http://localhost:8000/mcp/mcp.json/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"execute_shell_command","arguments":{"command":"ls -la tmp/newdir"}},"id":4}'
```

### Code Generation
```bash
# Generate code with OpenAI
curl -X POST http://localhost:8000/mcp/mcp.json/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"llm_generate_code_openai","arguments":{"prompt":"Write a Python function that adds two numbers.","language":"python"}},"id":5}'
```

---

## 🔒 Security Features

- **Authentication & Authorization** - Bearer token-based auth with role-based permissions
- **Sandboxed File Operations** - All file operations restricted to `shared_host_folder`
- **Audit Logging** - Comprehensive logging of all operations
- **Non-root Container Execution** - Docker containers run as non-privileged user
- **Configurable Shell Commands** - Shell execution can be disabled or restricted via allowlist
- **CORS Configuration** - Configurable cross-origin resource sharing

---

## 🐳 Docker Features

- **Fully Containerized** - Complete Docker support with optimized image
- **Volume Persistence** - Data and logs persist across container restarts
- **Health Checks** - Built-in health monitoring
- **Environment Configuration** - Flexible environment variable support
- **Multi-stage Build** - Optimized image size and security
- **Docker Compose** - Easy deployment with pre-configured setup

---

## 🧪 Testing

### Automated Docker Testing
```bash
./test_docker.sh
```

### Manual Testing
```bash
# Health check
curl http://localhost:8000/health

# Server info
curl http://localhost:8000/whoami

# Authentication
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

---

## 📝 API Endpoints

- `GET /health` - Health check
- `GET /whoami` - Server information
- `POST /api/auth/login` - Authentication
- `POST /api/adapters/{type}` - Create adapters
- `POST /api/adapters/{id}/execute` - Execute adapter requests
- `GET /mcp/mcp.json/` - MCP tools specification (requires auth)

---

## 🔧 Configuration

### Environment Variables

- `MCP_SERVER_PORT` - Server port (default: 8000)
- `MCP_BASE_WORKING_DIR` - Base working directory for sandboxed operations
- `AUDIT_LOG_FILE` - Path to audit log file
- `ENVIRONMENT` - Environment mode (development/staging/production)
- `ALLOW_ARBITRARY_SHELL_COMMANDS` - Enable/disable shell command execution
- `OPENAI_API_KEY` - OpenAI API key for code generation
- `GEMINI_API_KEY` - Google Gemini API key for code generation

---

## 🚨 Troubleshooting

### Common Issues

1. **Permission denied errors** - Ensure volume directories have proper permissions
2. **Port already in use** - Change the port mapping in docker-compose.yml
3. **API key errors** - Set the required environment variables for LLM tools
4. **Import errors** - Activate the virtual environment before running locally

### Development Obstacles & Solutions

**Correct JSON-RPC Calls**
- **Problem**: Early requests failed (HTTP 406/500), or tools weren't invoked.
- **Solution**: Updated all requests to use `"method": "tools/call"` and properly structure `"params": {"name": "...", "arguments": {...}}` per FastMCP documentation.

**Sandboxing & Path Security**
- **Problem**: Needed to prevent path traversal and unauthorized file access.
- **Solution**: Implemented strict path resolution and base directory checks in every file system tool.

**ASGI Task Group Initialization**
- **Problem**: RuntimeError: "Task group is not initialized. Make sure to use run()."
- **Solution**: Fixed app construction by passing `lifespan=mcp_app.lifespan` to the Starlette constructor.

**Docker Permission Issues**
- **Problem**: Audit log file couldn't be created due to non-root user permissions.
- **Solution**: Created dedicated logs directory with proper ownership and environment variable configuration.

---

## 📄 License

MIT License

---

## 🙏 Credits

- **FastMCP** - MCP server framework
- **OpenAI, Google Gemini API teams** - LLM integrations
- **Starlette/FastAPI** - ASGI framework
- **Developed by @SDIRISHGUY**