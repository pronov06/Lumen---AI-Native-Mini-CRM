#!/bin/bash
set -e

# Lumen Mini CRM Production Deployment Script
# Suitable for deployment on any Linux VM/VPS with Docker and Docker Compose installed.

echo "============================================="
echo "   Lumen Mini CRM Production Deployment      "
echo "============================================="

# 1. Determine Public IP or Domain
echo "Detecting public IP..."
PUBLIC_IP=$(curl -s https://ifconfig.me || echo "localhost")
echo "Default Public IP detected: $PUBLIC_IP"
read -p "Enter server public IP or domain name [$PUBLIC_IP]: " HOSTNAME
HOSTNAME=${HOSTNAME:-$PUBLIC_IP}

# 2. Extract Gemini API Key from local env if present
GEMINI_KEY=""
if [ -f "services/crm/.env" ]; then
    GEMINI_KEY=$(grep "CRM_GEMINI_API_KEY" services/crm/.env | cut -d'=' -f2)
fi

if [ -z "$GEMINI_KEY" ]; then
    read -p "Enter your Gemini API Key (press Enter to use offline local planner): " USER_KEY
    GEMINI_KEY=$USER_KEY
fi

# 3. Generate secure secrets
DB_PASS=$(openssl rand -hex 16 2>/dev/null || echo "xeno-secure-$(date +%s)")
CB_SECRET=$(openssl rand -hex 16 2>/dev/null || echo "cb-secret-$(date +%s)")

# 4. Write production .env file at root
echo "Creating root .env file for Docker Compose..."
cat <<EOF > .env
# --- Base Services ---
CALLBACK_SECRET=$CB_SECRET

# --- Databases ---
DB_USER=xeno
DB_PASSWORD=$DB_PASS
DB_NAME=xeno

# --- AI co-pilot ---
GEMINI_API_KEY=$GEMINI_KEY
GEMINI_MODEL=gemini-2.5-flash

# --- Frontend (baked into bundle at build time) ---
VITE_API_BASE=http://$HOSTNAME:8000
VITE_WS_BASE=ws://$HOSTNAME:8000

# --- CRM CORS Allowed Origins ---
CRM_CORS_ORIGINS=http://$HOSTNAME:8080,http://localhost:8080,http://localhost:5173
EOF

echo "✓ Created .env file with host configured to $HOSTNAME"

# 5. Run Docker Compose
echo "Starting production build and deployment..."
docker compose -f docker-compose.prod.yml down --remove-orphans || true
docker compose -f docker-compose.prod.yml up --build -d

# 6. Seed Database
echo "Waiting for services to startup..."
sleep 5

echo "Seeding the production PostgreSQL database..."
SEED_RESP=$(curl -s -X POST "http://localhost:8000/seed" \
  -H 'content-type: application/json' \
  -d '{"n_customers":240,"seed":7}' || echo "Failed to connect")

echo "Seed Response: $SEED_RESP"

echo "============================================="
echo "✓ Deployment complete!"
echo "Console available at: http://$HOSTNAME:8080"
echo "CRM API available at: http://$HOSTNAME:8000"
echo "Channel Simulator at: http://$HOSTNAME:8001"
echo "============================================="
