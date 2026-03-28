.PHONY: install test test-integration build build-image clean

install:
	uv venv && uv sync --extra dev

test:
	uv run pytest

test-integration:
	RUN_INTEGRATION=1 uv run pytest tests/test_integration.py -v -s

build-image:
	uv run python -c "from ankipush import build_image; build_image()"

build:
	uv build

clean:
	rm -rf .venv dist __pycache__ src/*.egg-info
