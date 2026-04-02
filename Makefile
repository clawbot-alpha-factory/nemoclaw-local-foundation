# NemoClaw Local Foundation — Development Commands
# Usage: make <target>

PYTHON = .venv313/bin/python3
UVICORN = .venv313/bin/uvicorn

.PHONY: validate test test-full backend frontend both skill lint audit ci-check clean help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

validate: ## Run 31-check validation suite
	$(PYTHON) scripts/validate.py

test: ## Run integration test (quick summary)
	$(PYTHON) scripts/integration_test.py --summary

test-full: ## Run integration test (verbose)
	$(PYTHON) scripts/integration_test.py --test

backend: ## Start FastAPI backend (port 8100)
	cd command-center/backend && ../../$(UVICORN) app.main:app --reload --port 8100

frontend: ## Start Next.js frontend (port 3000)
	cd command-center/frontend && npm run dev

both: ## Start backend + frontend
	$(MAKE) backend & $(MAKE) frontend

skill: ## Run a skill: make skill SKILL=research-brief
	$(PYTHON) skills/skill-runner.py --skill $(SKILL) --input-from skills/$(SKILL)/test-input.json

lint: ## Syntax check all Python files
	@echo "Checking syntax..."
	@errors=0; \
	for f in $$(find . -name "*.py" -not -path "./.venv313/*" -not -path "./tools/fish-speech/*" -not -path "./tools/capcut-api/*" -not -path "./.cc2-backup*/*" -not -path "./node_modules/*"); do \
		$(PYTHON) -c "import ast; ast.parse(open('$$f').read())" 2>/dev/null || { echo "  FAIL: $$f"; errors=$$((errors+1)); }; \
	done; \
	if [ $$errors -eq 0 ]; then echo "Lint: PASS (0 errors)"; else echo "Lint: FAIL ($$errors errors)"; exit 1; fi

audit: ## Run validation + integration test
	$(PYTHON) scripts/validate.py && $(PYTHON) scripts/integration_test.py --summary

ci-check: ## Run CI policy checks (L-003, quality gates, schema)
	$(PYTHON) scripts/ci_policy_check.py

clean: ## Remove checkpoints + __pycache__
	rm -f ~/.nemoclaw/checkpoints/langgraph.db
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	rm -rf ~/.nemoclaw/gamification
	@echo "Cleaned."

docker-build: ## Build Docker images
	docker compose build

docker-up: ## Start Docker containers
	docker compose up -d

docker-down: ## Stop Docker containers
	docker compose down
