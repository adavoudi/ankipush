.PHONY: install test build clean

install:
	uv venv && uv sync --extra dev

test:
	uv run pytest

build:
	uv build

clean:
	rm -rf .venv dist __pycache__ src/*.egg-info
