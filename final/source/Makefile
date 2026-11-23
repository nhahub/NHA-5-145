PYTHON ?= python3

.PHONY: store agent panel eval eval-browser install format format-check lint test build ci

store:
	pnpm --filter @shopping-copilot/store dev

agent:
	$(PYTHON) -m uvicorn agent.app:app --host 0.0.0.0 --port 8000 --reload

panel:
	pnpm --filter @shopping-copilot/panel dev

eval:
	$(PYTHON) -m pytest eval/tests

eval-browser:
	$(PYTHON) -m eval.runner

install:
	pnpm install --frozen-lockfile
	$(PYTHON) -m pip install -r requirements.lock

format:
	pnpm format:ts
	$(PYTHON) -m ruff format agent eval deploy

format-check:
	pnpm format:check:ts
	$(PYTHON) -m ruff format --check agent eval deploy

lint:
	pnpm lint:ts
	$(PYTHON) -m ruff check agent eval deploy

test:
	pnpm --recursive test
	$(PYTHON) -m pytest agent/tests eval/tests

build:
	pnpm --recursive build

ci: format-check lint test build
