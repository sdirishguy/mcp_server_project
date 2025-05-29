# Stage 1: Builder - To install dependencies
FROM python:3.13-slim-bookworm AS builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Create a non-root user and group for security
ARG APP_USER=appuser
ARG APP_GROUP=appgroup
ARG UID=1001
ARG GID=1001
RUN groupadd -g ${GID} ${APP_GROUP} || true && \
    useradd --create-home --uid ${UID} --gid ${APP_GROUP} --shell /bin/bash ${APP_USER}

WORKDIR /app

# Copy requirements.txt first to leverage Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt
# Note: The installed packages will be in /usr/local/lib/python3.13/site-packages/
# based on your diagnostic output.

# --- Final Stage ---
# Use the same base image for the final stage
FROM python:3.13-slim-bookworm AS final

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

ARG APP_USER=appuser
ARG APP_GROUP=appgroup

# Copy the created user/group from the builder stage
COPY --from=builder /etc/passwd /etc/passwd
COPY --from=builder /etc/group /etc/group
COPY --from=builder /home/${APP_USER} /home/${APP_USER}

# Copy installed Python packages from the builder stage's site-packages
# This path was confirmed by your diagnostic output
COPY --from=builder /usr/local/lib/python3.13/site-packages/ /usr/local/lib/python3.13/site-packages/

# Copy any executables that pip might have installed into system path (like pip itself if upgraded)
COPY --from=builder /usr/local/bin/ /usr/local/bin/

WORKDIR /app

# Copy the application code from the build context directly into the final stage
COPY ./app /app/app

# Create the default data directory and set ownership for the non-root user
# This is where MCP_BASE_WORKING_DIR defaults to, inside the container.
RUN mkdir -p /app/host_data && chown ${APP_USER}:${APP_GROUP} /app/host_data
# Ensure the entire /app directory is owned by the appuser for consistency
RUN chown -R ${APP_USER}:${APP_GROUP} /app

# Switch to the non-root user
USER ${APP_USER}:${APP_GROUP}

# Expose the port the app runs on (defined by MCP_SERVER_PORT, defaults to 3000)
# This is for documentation; actual port mapping is done with `docker run -p`
EXPOSE 3000

# Define the command to run the application
# This executes app/main.py. Using `python -m app.main` makes Python treat 'app' as a package.
CMD ["python", "-m", "app.main"]