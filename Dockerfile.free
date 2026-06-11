# Stage 1: Build the React web frontend
FROM node:22-alpine AS frontend-builder
WORKDIR /app
COPY web/package*.json ./web/
WORKDIR /app/web
RUN npm install
COPY web ./
RUN npm run build

# Stage 2: Runtime image packaging all services
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=7860

# Install Nginx, Supervisor, and curl for startup script healthchecks
RUN apt-get update && \
    apt-get install -y --no-install-recommends nginx supervisor curl && \
    rm -rf /var/lib/apt/lists/*

# Copy Nginx server configuration
COPY nginx.free.conf /etc/nginx/sites-available/default

# Adjust Nginx configurations to support non-root execution (UID 1000)
RUN sed -i 's/^user/#user/' /etc/nginx/nginx.conf && \
    sed -i 's|/var/run/nginx.pid|/tmp/nginx.pid|' /etc/nginx/nginx.conf && \
    mkdir -p /var/cache/nginx /var/lib/nginx /var/log/nginx /var/run/nginx && \
    chmod -R 777 /var/log/nginx /var/lib/nginx /var/cache/nginx /var/run/nginx


# Copy supervisord config
COPY supervisord.conf /etc/supervisor/supervisord.conf

# Set up backend applications
WORKDIR /srv
COPY services/crm/requirements.txt ./crm/
COPY services/channel/requirements.txt ./channel/

# Install Python backend dependencies
RUN pip install --no-cache-dir -r ./crm/requirements.txt && \
    pip install --no-cache-dir -r ./channel/requirements.txt

# Copy backend application codes
COPY services/crm/app ./crm/app
COPY services/channel/app ./channel/app

# Ensure /srv is fully writable for SQLite databases
RUN chmod -R 777 /srv

# Copy frontend static assets to Nginx html folder
COPY --from=frontend-builder /app/web/dist /var/www/html
RUN chmod -R 777 /var/www/html

# Set up entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose the default port (can be overridden by $PORT at runtime)
EXPOSE 7860

ENTRYPOINT ["/entrypoint.sh"]
