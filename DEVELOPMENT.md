# Development Guide

This guide covers the modern Python development setup for the Bench Finder project.

## Prerequisites

- Python 3.9 or higher
- [uv](https://docs.astral.sh/uv/) - Modern Python package manager
- Git

### Installing uv

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Or via pip
pip install uv
```

## Quick Start

1. **Clone and setup the development environment:**
   ```bash
   git clone <repository-url>
   cd bench_finder
   ./setup-dev.sh
   ```

2. **Or manually:**
   ```bash
   uv sync --dev
   uv run pre-commit install
   ```

## Development Workflow

### Code Quality

We use [Ruff](https://docs.astral.sh/ruff/) for linting and formatting, replacing mypy, black, isort, and flake8.

```bash
# Lint code
make lint
# or
uv run ruff check .

# Auto-fix linting issues
make lint-fix
# or
uv run ruff check --fix .

# Format code
make format
# or
uv run ruff format .

# Check formatting without changes
make format-check
# or
uv run ruff format --check .
```

### Testing

```bash
# Run tests
make test
# or
uv run pytest

# Run tests with coverage
make test-cov
# or
uv run pytest --cov=bench_finder --cov-report=html

# Run tests in watch mode
make test-watch
# or
uv run pytest-watch
```

### Pre-commit Hooks

Pre-commit hooks automatically run code quality checks before each commit:

```bash
# Run all pre-commit hooks manually
make pre-commit
# or
uv run pre-commit run --all-files

# Update pre-commit hooks
make pre-commit-update
# or
uv run pre-commit autoupdate
```

### Type Checking

We keep mypy for comprehensive type checking alongside ruff:

```bash
# Run type checking
make type-check
# or
uv run mypy bench_finder/ api/ tools/
```

### Security Checks

```bash
# Run security checks
make security
# or
uv run bandit -r bench_finder/ api/ tools/ -x tests/
```

## Available Commands

Use `make help` to see all available commands:

```bash
make help
```

### Common Development Commands

- `make dev` - Complete development workflow (lint, format, test)
- `make quick` - Quick development cycle
- `make all-checks` - Run all quality checks
- `make clean` - Clean temporary files and caches
- `make run-server` - Start FastAPI development server
- `make run-cli` - Run the bench-finder CLI

## Project Structure

```
bench_finder/
├── pyproject.toml          # Modern Python project configuration
├── .pre-commit-config.yaml # Pre-commit hooks configuration
├── Makefile               # Development commands
├── setup-dev.sh          # Development environment setup
├── bench_finder/         # Main application code
├── api/                  # API server code
├── tools/                # Utility tools
├── tests/                # Test suite
└── docs/                 # Documentation
```

## Configuration Files

### pyproject.toml

The `pyproject.toml` file contains:
- Project metadata and dependencies
- Ruff configuration for linting and formatting
- Pytest configuration
- Coverage settings
- MyPy configuration

### .pre-commit-config.yaml

Pre-commit hooks configuration including:
- Ruff linting and formatting
- Basic file checks (trailing whitespace, YAML syntax, etc.)
- Security checks with bandit
- Type checking with mypy

## IDE Integration

### VS Code

Recommended extensions:
- Python
- Ruff
- Pylance (for type checking)

VS Code settings (`.vscode/settings.json`):
```json
{
    "python.defaultInterpreterPath": "./.venv/bin/python",
    "python.linting.enabled": true,
    "python.linting.ruffEnabled": true,
    "python.formatting.provider": "none",
    "[python]": {
        "editor.formatOnSave": true,
        "editor.codeActionsOnSave": {
            "source.fixAll.ruff": true,
            "source.organizeImports.ruff": true
        }
    }
}
```

### PyCharm

1. Set Python interpreter to `.venv/bin/python`
2. Enable Ruff as external tool
3. Configure Ruff for formatting and linting

## Troubleshooting

### Common Issues

1. **uv not found**: Install uv using the instructions above
2. **Virtual environment issues**: Run `uv sync` to recreate the environment
3. **Pre-commit hooks failing**: Run `uv run pre-commit run --all-files` to see detailed errors
4. **Import errors**: Ensure you're using the virtual environment: `source .venv/bin/activate`

### Resetting Development Environment

```bash
make clean
rm -rf .venv/
./setup-dev.sh
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run the development workflow: `make dev`
5. Commit your changes (pre-commit hooks will run automatically)
6. Push and create a pull request

## Performance Tips

- Use `uv` instead of `pip` for faster package management
- Ruff is significantly faster than the tools it replaces
- Pre-commit hooks run in parallel when possible
- Use `make quick` for faster development cycles

## Migration from requirements.txt

The project has been migrated from `requirements.txt` to `pyproject.toml`. The old `requirements.txt` file can be removed after confirming everything works with the new setup.

Key changes:
- Dependencies are now in `pyproject.toml`
- Development dependencies are in optional dependencies
- Ruff replaces mypy, black, isort, and flake8
- uv replaces pip for package management
- Pre-commit hooks ensure code quality
