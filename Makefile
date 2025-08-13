SHELL := /bin/bash

.PHONY: dev fmt lint typecheck test coverage precommit

dev:
	@LOG_LEVEL=$${LOG_LEVEL:-INFO} python -m app.cli run --reload

fmt:
	@echo "🎨 Formatting with ruff..."
	@ruff check . --fix
	@ruff format .

lint:
	@echo "🔍 Linting with ruff..."
	@bash -c 'set -e; ruff check . & pid=$$!; sp="|/-\\"; i=0; \
	  while kill -0 $$pid 2>/dev/null; do i=$$(((i+1)%4)); \
	    printf "\r  $${sp:$$i:1} ruff running..."; sleep 0.2; done; \
	  printf "\r"; wait $$pid'

TYPECHECK_FLAGS=--config-file mypy.ini --pretty --show-column-numbers --show-error-codes --color-output
REPORT_DIR=.reports

typecheck:
	@mkdir -p $(REPORT_DIR)
	@echo "🔎 Running mypy..."
	@ts=$$(date +%Y%m%d-%H%M%S); \
	MYPY_FORCE_COLOR=1 mypy . $(TYPECHECK_FLAGS) | tee $(REPORT_DIR)/mypy-$$ts.log; \
	echo ""; \
	echo "📄 Full mypy report saved to: $(REPORT_DIR)/mypy-$$ts.log"; \
	grep -E "Found [0-9]+ errors|Success: no issues" $(REPORT_DIR)/mypy-$$ts.log || true

typecheck-open:
	@f=$$(ls -1t $(REPORT_DIR)/mypy-*.log 2>/dev/null | head -1); \
	if [ -z "$$f" ]; then echo "No mypy reports yet."; exit 1; fi; \
	echo "Opening $$f"; \
	$${PAGER:-less} -R "$$f"


test:
	@echo "🧪 Running pytest (progress bar, server up)..."
	@set -e; \
	PORT=$${PORT:-8000}; WAIT_SECS=$${WAIT_SECS:-60}; \
	LOG=.uvicorn_test.log; PIDF=.uvicorn_test.pid; READY=0; \
	if curl -sf "http://localhost:$$PORT/health" >/dev/null 2>&1; then \
	  echo "✅ Server already running on :$$PORT"; \
	else \
	  echo "🚀 Starting uvicorn on :$$PORT for tests..."; \
	  (uvicorn app.main:app --host 0.0.0.0 --port $$PORT --log-level info > $$LOG 2>&1 & echo $$! > $$PIDF); \
	  for i in $$(seq 1 $$((WAIT_SECS*5))); do \
	    if curl -sf "http://localhost:$$PORT/health" >/dev/null 2>&1; then READY=1; echo "✅ Server ready"; break; fi; \
	    printf "."; sleep 0.2; \
	  done; echo ""; \
	  if [ "$$READY" -ne 1 ]; then \
	    echo "❌ Timed out waiting for server on :$$PORT after $$WAIT_SECS seconds."; \
	    echo "—— Last 80 lines of $$LOG ——"; tail -n 80 $$LOG || true; \
	    echo "🛑 Stopping uvicorn (if started)..."; \
	    kill -TERM $$(cat $$PIDF 2>/dev/null) >/dev/null 2>&1 || true; rm -f $$PIDF; \
	    exit 1; \
	  fi; \
	fi; \
	PYTHONPATH=. pytest -v -ra --maxfail=1 --durations=10 || STATUS=$$?; \
	if [ -f .uvicorn_test.pid ]; then \
	  echo "🛑 Stopping uvicorn..."; \
	  kill -TERM $$(cat .uvicorn_test.pid) >/dev/null 2>&1 || true; \
	  rm -f .uvicorn_test.pid; \
	fi; \
	exit $${STATUS:-0}

coverage:
	@echo "📈 Running tests with coverage..."
	@PYTHONPATH=. pytest -v -ra --maxfail=1 --durations=10 -n auto --cov=app --cov-report=term-missing

precommit:
	pre-commit run -a
