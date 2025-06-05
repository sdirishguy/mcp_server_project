# Dockerfile

FROM python:3.12-slim

# System deps and setup
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Make a non-root user for safety
RUN useradd -ms /bin/bash appuser

# Workdir in the container
WORKDIR /app

# Requirements
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY app ./app
COPY test_mcp_client.py ./

# Create a host_data dir for persistent volumes and make it accessible
RUN mkdir -p /app/host_data && chown appuser:appuser /app/host_data

# Default to non-root user
USER appuser

# Expose MCP port (and FastAPI if you use it separately)
EXPOSE 8000

# Entrypoint: run the MCP server by default
CMD ["python", "-m", "app.main"]
