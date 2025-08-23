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
COPY shared_host_folder ./shared_host_folder

# Create directories for logs and data, and set proper permissions
RUN mkdir -p /app/logs /app/host_data && \
    chown -R appuser:appuser /app/logs /app/host_data /app/shared_host_folder

# Default to non-root user
USER appuser

# Expose MCP port (and FastAPI if you use it separately)
EXPOSE 8000

# Set environment variable for audit log location
ENV AUDIT_LOG_FILE=/app/logs/audit.log

# Entrypoint: run the MCP server by default
CMD ["python", "-m", "app.main"]


# Commands to run file
# docker build -t mcp-server .
# docker run -it --rm -p 8000:8000 -v $PWD/host_data:/app/host_data -v $PWD/logs:/app/logs mcp-server
