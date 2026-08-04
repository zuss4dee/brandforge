.DEFAULT_GOAL := help
.PHONY: help install fmt lint typecheck test boundaries inventory inventory-lock corpus check hooks clean

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: ## Sync the dev environment and install git hooks
	uv sync
	uv run pre-commit install

fmt: ## Format code
	uv run ruff format .
	uv run ruff check --fix .

lint: ## Lint without modifying files
	uv run ruff check .
	uv run ruff format --check .

typecheck: ## Type-check (strict)
	uv run mypy

test: ## Run the test suite
	uv run pytest

boundaries: ## Enforce the engine purity boundary (ADR-0006)
	uv run lint-imports

inventory: ## Verify ruleset inventories are append-only (ADR-0014)
	uv run python -m tools.inventory_lock check

inventory-lock: ## Regenerate inventory lockfiles — commit the diff
	uv run python -m tools.inventory_lock update

corpus: ## Licence, autophagy and holdout guards (ADR-0019)
	uv run python -m tools.check_corpus

check: lint typecheck boundaries inventory corpus test ## Everything CI runs

hooks: ## Run pre-commit across all files
	uv run pre-commit run --all-files

clean: ## Remove caches and build artifacts
	rm -rf .pytest_cache .mypy_cache .ruff_cache dist build .coverage
	find . -type d -name __pycache__ -not -path './.git/*' -exec rm -rf {} +
