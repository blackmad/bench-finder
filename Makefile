# Modern Python development Makefile for bench-finder
# Provides convenient commands for development workflow

.PHONY: help install dev-install lint format check test clean run-server run-cli setup-dev

# Default target
help: ## Show this help message
	@echo "Bench Finder Development Commands"
	@echo "================================="
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Installation commands
install: ## Install project dependencies using uv
	@echo "📦 Installing project dependencies..."
	uv sync

dev-install: ## Install development dependencies
	@echo "📦 Installing development dependencies..."
	uv sync --dev
	@echo "🔧 Setting up pre-commit hooks..."
	uv run pre-commit install

setup-dev: ## Complete development environment setup
	@echo "🚀 Setting up complete development environment..."
	./setup-dev.sh

# Code quality commands
lint: ## Run ruff linting
	@echo "🔍 Running ruff linting..."
	uv run ruff check .

lint-fix: ## Run ruff linting with auto-fix
	@echo "🔍 Running ruff linting with auto-fix..."
	uv run ruff check --fix .

format: ## Format code with ruff
	@echo "🎨 Formatting code with ruff..."
	uv run ruff format .

format-check: ## Check code formatting without making changes
	@echo "🎨 Checking code formatting..."
	uv run ruff format --check .

check: lint format-check ## Run all code quality checks
	@echo "✅ All code quality checks passed!"

# Testing commands
test: ## Run tests with pytest
	@echo "🧪 Running tests..."
	uv run pytest

test-cov: ## Run tests with coverage
	@echo "🧪 Running tests with coverage..."
	uv run pytest --cov=bench_finder --cov-report=html --cov-report=term

test-watch: ## Run tests in watch mode
	@echo "🧪 Running tests in watch mode..."
	uv run pytest-watch

# Pre-commit commands
pre-commit: ## Run all pre-commit hooks
	@echo "🔧 Running pre-commit hooks..."
	uv run pre-commit run --all-files

pre-commit-update: ## Update pre-commit hooks
	@echo "🔧 Updating pre-commit hooks..."
	uv run pre-commit autoupdate

# Application commands
run-server: ## Start the FastAPI development server
	@echo "🚀 Starting FastAPI development server..."
	uv run uvicorn api.fastapi_server:app --reload --host 0.0.0.0 --port 8866

run-frontend: ## Start the frontend development server (Vite)
	@echo "🚀 Starting frontend development server..."
	cd frontend && npm run dev

run-frontend-full: ## Start API and frontend together
	@echo "🚀 Starting API and frontend..."
	cd frontend && npm run dev:full

run-cli: ## Run the bench-finder CLI
	@echo "🔧 Running bench-finder CLI..."
	uv run bench-finder --help

# Utility commands
clean: ## Clean up temporary files and caches
	@echo "🧹 Cleaning up temporary files..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	rm -rf build/
	rm -rf dist/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf coverage.xml

clean-venv: ## Remove virtual environment
	@echo "🧹 Removing virtual environment..."
	rm -rf .venv/

# Development workflow commands
dev: ## Start development workflow (lint, format, test)
	@echo "🚀 Starting development workflow..."
	$(MAKE) lint-fix
	$(MAKE) format
	$(MAKE) test

ci: ## Run CI pipeline (check, test)
	@echo "🔄 Running CI pipeline..."
	$(MAKE) check
	$(MAKE) test

# Documentation commands
docs: ## Generate documentation (if applicable)
	@echo "📚 Generating documentation..."
	@echo "Documentation generation not yet implemented"

# Database commands
db-migrate: ## Run database migrations
	@echo "🗄️ Running database migrations..."
	uv run python -m bench_finder.migrate

# Type checking
type-check: ## Run type checking with mypy
	@echo "🔍 Running type checking..."
	uv run mypy bench_finder/ api/ tools/

# Security checks
security: ## Run security checks with bandit
	@echo "🔒 Running security checks..."
	uv run bandit -r bench_finder/ api/ tools/ -x tests/

# All-in-one commands
all-checks: lint format-check type-check security test ## Run all checks
	@echo "✅ All checks completed!"

# Quick development cycle
quick: lint-fix format test ## Quick development cycle (lint, format, test)
	@echo "⚡ Quick development cycle completed!"

# Show project info
info: ## Show project information
	@echo "Bench Finder Project Information"
	@echo "================================"
	@echo "Python version: $$(uv run python --version)"
	@echo "Ruff version: $$(uv run ruff --version)"
	@echo "Pytest version: $$(uv run pytest --version)"
	@echo "Project dependencies: $$(uv tree --depth 1 | wc -l) packages"
	@echo "Virtual environment: $$(if [ -d .venv ]; then echo "✅ Active"; else echo "❌ Not found"; fi)"
