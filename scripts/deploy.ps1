# Lumen Mini CRM Production Deployment Script (PowerShell)
# Suitable for Windows Server or local Docker environments

Write-Output "============================================="
Write-Output "   Lumen Mini CRM Production Deployment      "
Write-Output "============================================="

# 1. Determine Public IP or Domain
Write-Output "Detecting public IP..."
$publicIp = "localhost"
try {
    $publicIp = (Invoke-RestMethod -Uri "https://ifconfig.me" -TimeoutSec 3).Trim()
} catch {
    Write-Output "Could not resolve public IP, falling back to localhost."
}
Write-Output "Default Public IP detected: $publicIp"

$hostname = Read-Host "Enter server public IP or domain name [$publicIp]"
if ([string]::IsNullOrEmpty($hostname)) {
    $hostname = $publicIp
}

# 2. Extract Gemini API Key from local env if present
$geminiKey = ""
if (Test-Path "services/crm/.env") {
    $envLines = Get-Content "services/crm/.env"
    foreach ($line in $envLines) {
        if ($line -match "^CRM_GEMINI_API_KEY=(.*)") {
            $geminiKey = $Matches[1].Trim()
        }
    }
}

if ([string]::IsNullOrEmpty($geminiKey)) {
    $geminiKey = Read-Host "Enter your Gemini API Key (press Enter to use offline local planner)"
}

# 3. Generate secure secrets
$dbPass = [Convert]::ToBase64String((1..16 | ForEach-Object { [byte](Get-Random -Minimum 0 -Maximum 256) })) -replace '[^a-zA-Z0-9]', ''
$cbSecret = [Convert]::ToBase64String((1..16 | ForEach-Object { [byte](Get-Random -Minimum 0 -Maximum 256) })) -replace '[^a-zA-Z0-9]', ''

# 4. Write production .env file at root
Write-Output "Creating root .env file for Docker Compose..."
$envContent = @"
# --- Base Services ---
CALLBACK_SECRET=$cbSecret

# --- Databases ---
DB_USER=xeno
DB_PASSWORD=$dbPass
DB_NAME=xeno

# --- AI co-pilot ---
GEMINI_API_KEY=$geminiKey
GEMINI_MODEL=gemini-2.5-flash

# --- Frontend (baked into bundle at build time) ---
VITE_API_BASE=http://$hostname:8000
VITE_WS_BASE=ws://$hostname:8000

# --- CRM CORS Allowed Origins ---
CRM_CORS_ORIGINS=http://$hostname:8080,http://localhost:8080,http://localhost:5173
"@

$envContent | Out-File -FilePath ".env" -Encoding utf8

Write-Output "✓ Created .env file with host configured to $hostname"

# 5. Run Docker Compose
Write-Output "Starting production build and deployment..."
docker compose -f docker-compose.prod.yml down --remove-orphans
docker compose -f docker-compose.prod.yml up --build -d

# 6. Seed Database
Write-Output "Waiting for services to startup..."
Start-Sleep -Seconds 5

Write-Output "Seeding the production PostgreSQL database..."
try {
    $body = @{ n_customers = 240; seed = 7 } | ConvertTo-Json
    $seedResp = Invoke-RestMethod -Uri "http://localhost:8000/seed" -Method Post -Body $body -ContentType "application/json"
    Write-Output "Seed Response: $($seedResp | ConvertTo-Json -Compress)"
} catch {
    Write-Output "Failed to seed database: $_"
}

Write-Output "============================================="
Write-Output "✓ Deployment complete!"
Write-Output "Console available at: http://$hostname:8080"
Write-Output "CRM API available at: http://$hostname:8000"
Write-Output "Channel Simulator at: http://$hostname:8001"
Write-Output "============================================="
