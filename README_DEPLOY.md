# Deploying Lumen Mini CRM

This project is fully containerized and configured for production deployment using **Docker Compose** on a Linux VPS (e.g. AWS EC2, DigitalOcean Droplet, GCP VM) or a Windows Server.

---

## ⚡ Quick Start: Deploying with Scripts

We provide automation scripts that:
1. Detect your server's public IP.
2. Load your Gemini API Key automatically from your existing CRM `.env`.
3. Generate secure random passwords and secrets.
4. Build and run the containers using persistent production volumes (`pgdata` and `redisdata`).
5. Wait for the services to boot and seed the database with 240 customers and 984 orders.

### Option A: On a Linux VPS (Ubuntu/Debian)

Run the deployment script from the project root:
```bash
chmod +x scripts/deploy.sh
./scripts/deploy.sh
```

### Option B: On Windows Server (PowerShell)

Run the deployment script from PowerShell (run as Administrator if needed):
```powershell
.\scripts\deploy.ps1
```

---

## 🏗️ Production Architecture (`docker-compose.prod.yml`)

The production compose file differs from local development by:
*   **Data Persistence**: Postgres and Redis are wired to persistent named volumes (`pgdata` and `redisdata`) so that data is preserved when containers stop, update, or restart.
*   **Auto-Restart**: All services use `restart: always` to recover from crashes or system reboots.
*   **Secrets Management**: Auto-generates random database passwords and HMAC signature callback secrets during deploy time rather than relying on defaults.

---

## 🔒 Production Hardening & SSL (Nginx Reverse Proxy)

In production, exposing ports `8000`, `8001`, and `8080` directly to the internet is not secure. Instead, run an Nginx reverse proxy on the host to listen on port `80` (HTTP) and `443` (HTTPS) with SSL certificates from Let's Encrypt.

Here is a recommended Nginx configuration block (`/etc/nginx/sites-available/lumen`) to route all traffic securely:

```nginx
server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # Frontend Console (Vite React App)
    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # CRM Backend API
    location ~ ^/(seed|customers|campaigns|receipts|dead-letters|copilot) {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # CRM WebSocket feed
    location /ws/feed {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

> [!TIP]
> When using a reverse proxy with SSL, remember to run `./scripts/deploy.sh` (or `deploy.ps1`) and enter `yourdomain.com` (without `http` or `ws` prefixes) when prompted for the server hostname. The scripts will automatically wire up `https://yourdomain.com` and `wss://yourdomain.com` for the frontend.
