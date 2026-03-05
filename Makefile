.PHONY: install infra-up infra-down verify run-supervisor run-web run-robot test

VENV_PYTHON := .venv/bin/python

install:
	python -m venv .venv
	$(VENV_PYTHON) -m pip install -r requirements.txt

infra-up:
	docker compose up -d

infra-down:
	docker compose down

verify:
	$(VENV_PYTHON) scripts/verify_runtime.py

run-supervisor:
	$(VENV_PYTHON) -m supervisor.tcp_server

run-web:
	.venv/bin/uvicorn supervisor.web_monitor:app --host 0.0.0.0 --port 8000

run-robot:
	$(VENV_PYTHON) -m robots.tcp_client

test:
	$(VENV_PYTHON) -m pytest -q
