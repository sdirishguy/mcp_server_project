# Stage 1: Builder - To install dependencies
FROM python:3.13-slim-bookworm AS builder

# Set environment variables for Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Create a non-root user and group for security
ARG APP_USER=appuser
ARG APP_GROUP=appgroup
ARG UID=1001
ARG GID=1001
# Ensure group is created first, then user. || true prevents error if group/user already exists (less likely in clean build)
RUN groupadd -g ${GID} ${APP_GROUP} || true && \
    useradd --create-home --uid ${UID} --gid ${APP_GROUP} --shell /bin/bash ${APP_USER}

# Set working directory for the builder stage
WORKDIR /build_temp_app

# Copy requirements.txt first to leverage Docker layer caching
COPY requirements.txt .

# Install Python dependencies
# Ensure requirements.txt contains "mcp[cli]", "uvicorn[standard]", "starlette", etc.
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# --- Final Stage ---
# Use the same base image for the final stage for consistency
FROM python:3.13-slim-bookworm AS final

# Set environment variables for Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Copy the created user and group from the builder stage
ARG APP_USER=appuser
ARG APP_GROUP=appgroup
COPY --from=builder /etc/passwd /etc/passwd
COPY --from=builder /etc/group /etc/group
# Copy the user's home directory (might contain pip cache configs or other user-specific things if any)
COPY --from=builder /home/${APP_USER} /home/${APP_USER}

# Copy installed Python packages from the builder stage
COPY --from=builder /usr/local/lib/python3.13/site-packages/ /usr/local/lib/python3.13/site-packages/
# Copy any executables that pip might have installed (like mcp, uvicorn, pip itself if upgraded)
COPY --from=builder /usr/local/bin/ /usr/local/bin/

# Set up the application directory structure and PYTHONPATH
# /app_code will be the root for our application package structure.
# Add /app_code to Python's module search path
ENV PYTHONPATH="/app_code:${PYTHONPATH}"
WORKDIR /app_code # Set the working directory

# Copy your local ./app directory (which contains __init__.py, main.py, config.py, tools.py)
# into a subdirectory named 'app' inside /app_code.
# This creates the package structure: /app_code/app/main.py, etc.
COPY ./app /app_code/app

# Create the host_data directory (where volume mounts might go, relative to your app code)
# and set permissions for the non-root user.
RUN mkdir -p /app_code/app/host_data && chown ${APP_USER}:${APP_GROUP} /app_code/app/host_data
# Ensure the entire /app_code directory (including your 'app' package) is owned by appuser
RUN chown -R ${APP_USER}:${APP_GROUP} /app_code

# Switch to the non-root user
USER ${APP_USER}:${APP_GROUP}

# Expose the port the app runs on (MCP_SERVER_PORT is set by `docker run -e`)
# This default in EXPOSE is mainly for documentation.
EXPOSE 3000 

# CMD to run the 'main' module within the 'app' package.
# Python will look for the 'app' package in PYTHONPATH (which includes /app_code).
# It finds /app_code/app/, then runs main.py from within it as a module.
# The "if __name__ == '__main__':" block in /app_code/app/main.py will execute.
CMD ["python", "-m", "app.main"]