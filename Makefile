.PHONY: all
all:

# Worktree isolation: set WORKTREE_ID=<n> to run a parallel dev stack.
# WORKTREE_ID=0 (default) uses standard ports. Each increment adds 100.
# Example: WORKTREE_ID=1 make dev  → ports 8180, 9100, 8100, 3100, etc.
WORKTREE_ID ?= 0
COMPOSE_PROJECT_NAME ?= kartograph-wt$(WORKTREE_ID)

PORT_OFFSET := $(shell expr $(WORKTREE_ID) \* 100)
KEYCLOAK_PORT     := $(shell expr 8080 + $(PORT_OFFSET))
KEYCLOAK_HEALTH_PORT := $(shell expr 9000 + $(PORT_OFFSET))
SPICEDB_PORT      := $(shell expr 50051 + $(PORT_OFFSET))
POSTGRES_PORT     := $(shell expr 5432 + $(PORT_OFFSET))
API_PORT          := $(shell expr 8000 + $(PORT_OFFSET))
DEV_UI_PORT       := $(shell expr 3000 + $(PORT_OFFSET))
DEV_UI_HMR_PORT   := $(shell expr 24678 + $(PORT_OFFSET))

# Export all port vars and project name for docker compose
COMPOSE_ENV := COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) \
	KEYCLOAK_PORT=$(KEYCLOAK_PORT) \
	KEYCLOAK_HEALTH_PORT=$(KEYCLOAK_HEALTH_PORT) \
	SPICEDB_PORT=$(SPICEDB_PORT) \
	POSTGRES_PORT=$(POSTGRES_PORT) \
	API_PORT=$(API_PORT) \
	DEV_UI_PORT=$(DEV_UI_PORT) \
	DEV_UI_HMR_PORT=$(DEV_UI_HMR_PORT)

.PHONY: certs
certs:
	@echo "[Certificates] Generating self-signed certificates for SpiceDB..."
	@mkdir -p certs
	@if [ ! -f certs/spicedb-cert.pem ] || [ ! -f certs/spicedb-key.pem ]; then \
		openssl req -x509 -newkey rsa:4096 \
			-keyout certs/spicedb-key.pem \
			-out certs/spicedb-cert.pem \
			-days 365 -nodes \
			-subj "/CN=spicedb/O=Kartograph Dev" \
			-addext "subjectAltName=DNS:spicedb,DNS:localhost,IP:127.0.0.1"; \
		chmod 555 certs/spicedb-cert.pem certs/spicedb-key.pem; \
		echo "Certificates generated in certs/"; \
		echo "  Available for local tests via certs/spicedb-cert.pem"; \
	else \
		echo "Certificates already exist in certs/"; \
	fi

.PHONY: dev
dev: certs
	@echo "[Development] Starting application containers (project=$(COMPOSE_PROJECT_NAME))..."
	$(COMPOSE_ENV) docker compose -f compose.yaml build
	$(COMPOSE_ENV) docker compose -f compose.yaml -f compose.dev.yaml --profile ui up -d
	@echo "Done."
	@echo "----------------------------"
	@echo "API Root: http://localhost:$(API_PORT)"
	@echo "API Docs: http://localhost:$(API_PORT)/docs/"
	@echo "Dev UI:   http://localhost:$(DEV_UI_PORT)"
	@echo "----------------------------"

.PHONY: down
down:
	$(COMPOSE_ENV) docker compose -f compose.yaml -f compose.dev.yaml down


.PHONY: run
run:
	@echo "[Non-Development] Starting application containers (project=$(COMPOSE_PROJECT_NAME))..."
	$(COMPOSE_ENV) docker compose -f compose.yaml build
	$(COMPOSE_ENV) docker compose -f compose.yaml up -d
	@echo "Done."
	@echo "----------------------------"
	@echo "API Root: http://localhost:$(API_PORT)"
	@echo "API Docs: http://localhost:$(API_PORT)/docs/"
	@echo "----------------------------"


.PHONY: logs
logs:
	$(COMPOSE_ENV) docker compose logs --tail 1000 --follow

.PHONY: docs-export
docs-export:
.PHONY: docs-export
docs-export:
	@echo "Exporting system properties to JSON..."
	cd src/api && uv run python ../../scripts/export_system_properties.py
	@echo "Exporting environment variables to JSON..."
	cd src/api && uv run python ../../scripts/export_settings.py

# Internal helper: print a single variable value (used by test-worktree-isolation.sh)
_print-%:
	@echo $($*)

.PHONY: test-worktree-isolation
test-worktree-isolation:
	@bash scripts/test-worktree-isolation.sh

.PHONY: docs
docs: docs-export
	@echo "Starting documentation dev server..."
	cd website && npm i && npm run dev
