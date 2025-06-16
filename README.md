# MCP Server Project

A **Model Context Protocol (MCP) Server** for secure, programmable agent tools over HTTP, built with Python 3.13, FastMCP, and Starlette/FastAPI.

Ideal for orchestrating local or remote AI agent workflows, automating file and shell operations, and integrating with LLM APIs.

---

## 🚀 Overview

This server exposes modular tools—filesystem, shell, and LLM code generation—via JSON-RPC over HTTP with robust sandboxing and modern ASGI architecture.

**Deploy anywhere**: local dev, cloud, or container, and easily plug in new tools as your agents grow.

---

## 🗂️ Project Structure


mcp_server_project/
├── app/
│ ├── main.py # Entry point (ASGI app, tool registration)
│ ├── tools.py # All tool handlers
│ └── config.py # Env/config management
├── Dockerfile
├── requirements.txt
├── README.md
├── shared_host_folder/
├── tests/
│ ├── test_mcp.py
│ └── test_mcp_client.py
└── ...
## 📦 Requirements

### Software

- **Python 3.13+** (Tested on 3.13)
- **pip** (Python package manager)
- **Docker** *(optional, for container deployment)*
- **Git** (for cloning repo)

### Python Libraries

Put these in your `requirements.txt`:

fastmcp>=1.9.1
starlette
uvicorn
httpx
pydantic
pydantic-settings
python-multipart
anyio
sse-starlette
openai # (Optional: only if using OpenAI API features)

yaml
Copy
Edit

**Note:** Some libraries like `openai` are optional; only install if you’ll use those features.

---

## 🛠️ Installation & Setup

**1. Clone the repo:**

git clone https://github.com/SDIRISHGUY/MCP_SERVER_PROJECT.git
cd MCP_SERVER_PROJECT

2. Set up a Python virtual environment:
python3 -m venv .venv
source .venv/bin/activate

3. Install dependencies:

pip install -r requirements.txt
(If you don’t have a requirements.txt yet, manually install the list above.)

4. (Optional) Set environment variables for LLMs:

export OPENAI_API_KEY=sk-...
export GEMINI_API_KEY=...

5. Start the server:

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

🧪 Example Tool Calls

Create Directory
curl -X POST http://localhost:8000/api/mcp.json/ \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"file_system_create_directory","arguments":{"path":"tmp/newdir"}},"id":1}'

Write File
curl -X POST http://localhost:8000/api/mcp.json/ \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"file_system_write_file","arguments":{"path":"tmp/newdir/hello.txt","content":"Hello, world!"}},"id":2}'

Read File
curl -X POST http://localhost:8000/api/mcp.json/ \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"file_system_read_file","arguments":{"path":"tmp/newdir/hello.txt"}},"id":3}'

List Directory
curl -X POST http://localhost:8000/api/mcp.json/ \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"file_system_list_directory","arguments":{"path":"tmp/newdir"}},"id":4}'

Execute Shell Command
curl -X POST http://localhost:8000/api/mcp.json/ \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"execute_shell_command","arguments":{"command":"ls -la tmp/newdir"}},"id":5}'

Generate Code (OpenAI)
curl -X POST http://localhost:8000/api/mcp.json/ \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"llm_generate_code_openai","arguments":{"prompt":"Write a Python function that adds two numbers.","language":"python"}},"id":6}'


⚠️ Development Obstacles & Solutions

Correct JSON-RPC Calls

Problem: Early requests failed (HTTP 406/500), or tools weren’t invoked.

Solution: Updated all requests to use "method": "tools/call" and properly structure "params": {"name": "...", "arguments": {...}} per FastMCP documentation.

Sandboxing & Path Security

Problem: Needed to prevent path traversal and unauthorized file access.

Solution: Implemented strict path resolution and base directory checks in every file system tool.

ASGI Task Group Initialization

Problem: RuntimeError: “Task group is not initialized. Make sure to use run().”

Solution: Fixed app construction by passing lifespan=mcp_app.lifespan to the Starlette constructor.


📝 License
MIT License

🙏 Credits
FastMCP

OpenAI, Google Gemini API teams

Developed by @SDIRISHGUY