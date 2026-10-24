# Targets assume Linux/WSL2 and a uv-managed venv at .venv. Untested in this scaffold commit.
PY := .venv/bin/python
UV := uv pip install --python $(PY)

.PHONY: setup up down api worker web test lint gen-data

setup:
	uv python install 3.11
	test -d .venv || uv venv --python 3.11 .venv
	$(UV) -e . -r requirements/dev.txt -r requirements/extraction.txt -r requirements/provenance.txt \
		-r requirements/forensics.txt -r requirements/reasoning.txt -r requirements/ledger.txt \
		-r requirements/synthetic.txt

up:
	docker compose -f infra/docker-compose.yml up -d

down:
	docker compose -f infra/docker-compose.yml down

api:
	$(PY) -m uvicorn services.api.main:app --reload --port 8000

worker:
	$(PY) -m celery -A services.worker.app worker -l info

web:
	cd apps/web && npm run dev

test:
	$(PY) -m pytest -m "not slow"

lint:
	$(PY) -m ruff check . && $(PY) -m ruff format --check .

gen-data:
	$(PY) -m docverf.synthetic --out data/synthetic --n 20
