.PHONY: install infra-up infra-down verify generate-grpc run-supervisor run-web run-grpc run-robot grpc-demo test

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

generate-grpc:
	$(VENV_PYTHON) scripts/generate_grpc_stubs.py

run-supervisor:
	$(VENV_PYTHON) -m supervisor.tcp_server

run-web:
	.venv/bin/uvicorn supervisor.web_monitor:app --host 0.0.0.0 --port 8000

run-grpc:
	$(VENV_PYTHON) -m supervisor.grpc_server

run-robot:
	$(VENV_PYTHON) -m robots.tcp_client

grpc-demo:
	$(VENV_PYTHON) scripts/grpc_demo_client.py

test:
	$(VENV_PYTHON) -m pytest -q
