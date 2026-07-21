PYTHON_RUN := uv run --frozen

.PHONY: sync test

sync:
	uv sync --frozen

test: sync
	$(PYTHON_RUN) python -m pytest -q
