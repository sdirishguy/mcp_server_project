FROM python:3.12-slim-bookworm

# System prep (optional but common)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create appuser (not root)
ARG APP_USER=appuser
ARG APP_GROUP=appgroup
ARG UID=1001
ARG GID=1001
RUN groupadd -g ${GID} ${APP_GROUP} && \
    useradd --create-home --uid ${UID} --gid ${APP_GROUP} --shell /bin/bash ${APP_USER}

# Set workdir
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy your code
COPY ./app /app/app

# (Optional: for persistent data mount)
RUN mkdir -p /app/shared_host_folder && chown ${APP_USER}:${APP_GROUP} /app/shared_host_folder
RUN chown -R ${APP_USER}:${APP_GROUP} /app

USER ${APP_USER}:${APP_GROUP}

EXPOSE 3000

CMD ["python", "-m", "app.main"]
