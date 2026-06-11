#!/bin/bash
set -e

# Port configuration (default to 7860 for Hugging Face Spaces compatibility)
PORT=${PORT:-7860}
echo "Configuring Nginx to listen on port $PORT..."
sed -i "s/listen 7860;/listen $PORT;/g" /etc/nginx/sites-available/default

# Auto-seed database once the CRM API is online
(
    echo "Waiting for CRM API to start up to check seeding status..."
    for i in {1..30}; do
        if curl -s http://127.0.0.1:8000/health | grep -q "crm"; then
            echo "CRM API is up! Checking database..."
            CUSTOMER_COUNT=$(curl -s http://127.0.0.1:8000/customers | grep -o '"total":[0-9]*' | grep -o '[0-9]*' || echo "0")
            if [ "$CUSTOMER_COUNT" = "0" ] || [ -z "$CUSTOMER_COUNT" ]; then
                echo "No customers found. Seeding database..."
                curl -s -X POST http://127.0.0.1:8000/seed \
                     -H "Content-Type: application/json" \
                     -d '{"n_customers": 240, "seed": 7}'
                echo "Database seeded successfully with 240 customers and 984 orders!"
            else
                echo "Database already contains $CUSTOMER_COUNT customers. Skipping auto-seed."
            fi
            break
        fi
        sleep 2
    done
) &

echo "Starting Supervisor..."
exec /usr/bin/supervisord -n -c /etc/supervisor/supervisord.conf
