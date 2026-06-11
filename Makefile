.PHONY: help up down logs test test-crm dev-crm dev-channel dev-web seed clean

help:
	@echo "Targets:"
	@echo "  up           docker compose up --build (full stack on :8080)"
	@echo "  down         stop and remove containers"
	@echo "  logs         tail all service logs"
	@echo "  test         run the CRM test suite (domain + integration + e2e)"
	@echo "  dev-crm      run the CRM locally on :8000 (SQLite, in-process bus)"
	@echo "  dev-channel  run the channel simulator locally on :8001"
	@echo "  dev-web      run the Vite dev server on :5173"
	@echo "  seed         POST /seed to a locally-running CRM"

up:
	docker compose up --build

down:
	docker compose down -v

logs:
	docker compose logs -f

test:
	cd services/crm && python -m pytest -q

# --- local dev (no Docker) -----------------------------------------------------
# Each service is independent. Run these in separate terminals.

dev-channel:
	cd services/channel && \
	CHANNEL_CALLBACK_SECRET=dev-shared-secret \
	uvicorn app.main:app --reload --port 8001

dev-crm:
	cd services/crm && \
	CRM_CALLBACK_SECRET=dev-shared-secret \
	CRM_CHANNEL_BASE_URL=http://127.0.0.1:8001 \
	CRM_CRM_PUBLIC_URL=http://127.0.0.1:8000 \
	uvicorn app.main:app --reload --port 8000

dev-web:
	cd web && npm install && npm run dev

seed:
	curl -s -X POST http://127.0.0.1:8000/seed \
	  -H 'content-type: application/json' \
	  -d '{"n_customers":240,"seed":7}' | python -m json.tool

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type f -name '*.db' -delete
