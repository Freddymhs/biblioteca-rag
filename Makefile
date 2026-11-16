# Atajos de calidad. Todos corren dentro del entorno de uv.
.PHONY: lint typecheck test check

lint:
	uv run ruff check .
	uv run ruff format --check .

typecheck:
	uv run pyright

test:
	uv run pytest

check: lint typecheck test
