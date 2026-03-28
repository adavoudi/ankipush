.PHONY: install test test-integration build clean

install:
	uv venv && uv sync --extra dev

test:
	uv run pytest

test-integration:
	RUN_INTEGRATION=1 uv run pytest tests/test_integration.py -v

build:
	uv build

clean:
	rm -rf .venv dist __pycache__ src/*.egg-info
