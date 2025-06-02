<<<<<<< HEAD
# Python MCP Server Project

## Description

This project implements a Model Context Protocol (MCP) server using Python. The server is built with the `mcp` Python SDK (leveraging `FastMCP`), served via Uvicorn and Starlette, and is fully containerized using Docker.

The primary purpose of this server is to expose local capabilities (like file system access and command execution) to MCP clients, such as AI agents or language models, enabling them to interact with the local environment in a structured and secure way.

Current features include tools for:
* File system directory creation
* File writing
* File reading
* Directory content listing
* Shell command execution (within the container)

## Features

The server currently exposes the following tools via MCP:

1.  **`file_system_create_directory`**: Creates a new directory.
    * **Input:** `{"path": "string"}` (relative to the server's base working directory)
2.  **`file_system_write_file`**: Writes content to a file.
    * **Input:** `{"path": "string", "content": "string"}` (path is relative)
3.  **`file_system_read_file`**: Reads content from a file.
    * **Input:** `{"path": "string"}` (path is relative)
4.  **`file_system_list_directory`**: Lists files and subdirectories.
    * **Input:** `{"path": "string"}` (path is relative; `.` for base directory)
5.  **`execute_shell_command`**: Executes a shell command inside the container.
    * **Input:** `{"command": "string", "working_directory": "string" (optional, relative)}`

## Technology Stack

* **Python:** 3.13 (as per Docker base image `python:3.13-slim-bookworm`)
* **MCP SDK:** `mcp[cli]` package (version 1.9.1 or as specified in `requirements.txt`)
    * Utilizes `FastMCP` for server implementation.
* **ASGI Server:** Uvicorn
* **ASGI Framework:** Starlette (for mounting MCP sub-applications and custom routes like `/health`)
* **Containerization:** Docker
* **Development Environment:** WSL2 (Ubuntu) on Windows 11

## Project Structure

mcp_server_project/
├── app/                  # Python application source code
│   ├── init.py       # Makes 'app' a Python package
│   ├── main.py           # Main server logic (FastMCP, Starlette, Uvicorn setup)
│   ├── tools.py          # Implementation of the MCP tools
│   └── config.py         # Configuration handling (ports, paths from env vars)
├── Dockerfile            # Defines how to build the Docker image
├── requirements.txt      # Python dependencies for the server
├── .dockerignore         # Specifies files for Docker to ignore during build
├── shared_host_folder/   # Example directory to volume mount into the container
├── test_mcp_client.py    # Example Python test client script
└── README.md             # This file


## Prerequisites

* **Docker Desktop:** Installed and running, with WSL2 integration enabled for your Linux distribution.
* **WSL2:** With a Linux distribution (e.g., Ubuntu) installed.
* **Git:** For cloning the repository (if applicable).
* **Python 3.12+ with `venv` (for the test client):** To run `test_mcp_client.py` locally in your WSL2 environment.

## Setup

1.  **Clone the Repository (if applicable):**
    ```bash
    git clone <your-repo-url>
    cd mcp_server_project
    ```
2.  **Ensure Project Files Are Present:**
    Make sure you have all the files listed in the "Project Structure" section, especially the `app/` directory content, `Dockerfile`, and `requirements.txt`.
3.  **Create Shared Host Folder:**
    Create the directory on your host machine that will be mounted into the container. For example:
    ```bash
    mkdir shared_host_folder
    ```
    (This corresponds to `D:\mcp_server_project\shared_host_folder` on your Windows host, accessible as `/mnt/d/mcp_server_project/shared_host_folder` from WSL2).

## Building the Docker Image

Navigate to the project root directory (where the `Dockerfile` is located) in your WSL2 Ubuntu terminal and run:

```bash
docker build -t mcp-server .
Use docker build --no-cache -t mcp-server . if you need to ensure all layers are rebuilt (e.g., after changing requirements.txt or base images).

Running the Server
Once the image is built, run the Docker container:

Bash

docker run -d \
    -p 3000:3000 \
    --name my-mcp-server-instance \
    -e MCP_SERVER_PORT=3000 \
    -e MCP_BASE_WORKING_DIR="/app_code/app/host_data" \
    -e ALLOW_ARBITRARY_SHELL_COMMANDS="true" \
    -v "/mnt/d/mcp_server_project/shared_host_folder:/app_code/app/host_data" \
    mcp-server
Explanation of docker run arguments:

-d: Run in detached mode (background).
-p 3000:3000: Map port 3000 on your host to port 3000 in the container.
--name my-mcp-server-instance: Assign a name to the container.
-e MCP_SERVER_PORT=3000: Sets the port the server listens on inside the container. Must match the container-side port in the -p mapping.
-e MCP_BASE_WORKING_DIR="/app_code/app/host_data": Sets the base directory inside the container for file system tools. This path should match the container-side path of your volume mount if you intend for tools to operate on mounted host files. The Dockerfile creates /app_code/app/host_data.
-e ALLOW_ARBITRARY_SHELL_COMMANDS="true": Set to "true" to enable the execute_shell_command tool. Warning: Be cautious with this if exposing the server.
-v "/mnt/d/mcp_server_project/shared_host_folder:/app_code/app/host_data": Mounts a directory from your host (WSL2 path) into the container.
Replace /mnt/d/mcp_server_project/shared_host_folder with the actual path to your shared folder in WSL2.
The container path /app_code/app/host_data should match MCP_BASE_WORKING_DIR.
mcp-server: The name of the Docker image to run.
Check Logs:

Bash

docker logs -f my-mcp-server-instance
You should see Uvicorn starting and listening on http://0.0.0.0:3000.

Testing the Server
1. Health Check
Once the server is running, you can test its health endpoint from your host machine's browser or curl:

Bash

curl -i http://localhost:3000/health
Expected response: {"status":"ok","message":"MCP Server (Starlette + FastMCP) is healthy."}

2. Basic MCP Endpoint Check
You can curl the primary MCP endpoint. It might redirect or expect specific MCP headers/methods, but it shouldn't give a fundamental server error if the server is running correctly.

Bash

curl -i http://localhost:3000/mcp/
(Note the trailing slash, as the server might redirect to it). You might see headers for text/event-stream and the connection might hang, which is normal for an SSE endpoint.

3. Using the Python Test Client (test_mcp_client.py)
A Python script test_mcp_client.py is provided (or should be created by you) to perform more comprehensive tests of the MCP tools.

Setup Client Environment (in your WSL2 Ubuntu terminal, outside Docker):
Navigate to your project directory: cd /mnt/d/mcp_server_project
Create a Python virtual environment (if you haven't already):
Bash

python3 -m venv .venv
source .venv/bin/activate
Install client dependencies into the virtual environment:
Bash

pip install "mcp[cli]>=1.9.1" httpx httpx-sse # Or just 'mcp' and other specific needs
Run the Test Client: Make sure your MCP server Docker container is running. Then, from the activated virtual environment:
Bash

python3 test_mcp_client.py
The client will attempt to connect, initialize, list tools, and call each tool with sample parameters, printing the results.
Configuration
The server can be configured using environment variables passed via the docker run -e flag:

MCP_SERVER_PORT: (Default: 3000) The port the server listens on inside the container.
MCP_BASE_WORKING_DIR: (Default in app/config.py is currently /app/host_data, but your docker run uses /app_code/app/host_data). This is the base directory within the container for file system tools. It should match your volume mount's container-side path if you want tools to interact with mounted host files.
ALLOW_ARBITRARY_SHELL_COMMANDS: (Default: true in the example docker run) Set to "false" to disable the execute_shell_command tool for security.
Future Goals / TODO
Develop more sophisticated tools tailored for:
Code generation and modification.
Interacting with Git repositories.
Cybersecurity automation scripts.
Managing ethical hacking lab environments.
Build an MCP client/agent, potentially as a Sublime Text plugin.
Integrate with Large Language Models (LLMs) for task decomposition and tool orchestration.
Explore monetization strategies for advanced capabilities.
Refine error handling and security hardening.
