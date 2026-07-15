.PHONY: setup test lint api demo cloud-demo benchmark

setup:
	uv sync --extra dev --extra backblaze

test:
	PYTHONPATH=src .venv/bin/pytest -q

lint:
	.venv/bin/ruff check src tests

api:
	PYTHONPATH=src .venv/bin/uvicorn reproframe.api:app --reload --host 127.0.0.1 --port 8000

demo:
	PYTHONPATH=src .venv/bin/python -m reproframe.cli demo

cloud-demo:
	PYTHONPATH=src .venv/bin/python -m reproframe.cli cloud-demo

benchmark:
	PYTHONPATH=src .venv/bin/python -m reproframe.cli benchmark
