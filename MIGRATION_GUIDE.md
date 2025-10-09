# Migration Guide: From requirements.txt to Modern Python Tooling

This guide helps you migrate from the old `requirements.txt` setup to the new modern Python development environment.

## What Changed

### ✅ New Modern Setup
- **pyproject.toml**: All dependencies and project configuration in one file
- **uv**: Fast Python package manager (replaces pip)
- **Ruff**: Ultra-fast linter and formatter (replaces mypy, black, isort, flake8)
- **Pre-commit hooks**: Automated code quality checks
- **Makefile**: Convenient development commands

### ❌ Removed
- `requirements.txt` (backed up as `requirements.txt.backup`)
- Manual mypy configuration
- Separate black/isort configuration

## Migration Steps

### 1. Install uv (if not already installed)

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Or via pip
pip install uv
```

### 2. Set up the new environment

```bash
# Remove old virtual environment (if exists)
rm -rf venv/

# Set up new environment with uv
./setup-dev.sh
```

### 3. Update your workflow

#### Old Commands → New Commands

| Old Command | New Command | Description |
|-------------|-------------|-------------|
| `pip install -r requirements.txt` | `uv sync` | Install dependencies |
| `pip install -r requirements.txt --dev` | `uv sync --dev` | Install with dev dependencies |
| `mypy .` | `make lint` or `uv run ruff check .` | Linting |
| `black .` | `make format` or `uv run ruff format .` | Code formatting |
| `isort .` | `uv run ruff check --fix .` | Import sorting |
| `flake8 .` | `uv run ruff check .` | Style checking |
| `pytest` | `make test` or `uv run pytest` | Run tests |

#### New Convenience Commands

```bash
make help          # Show all available commands
make dev           # Complete development workflow
make quick         # Quick development cycle
make all-checks    # Run all quality checks
make clean         # Clean temporary files
```

### 4. IDE Configuration

#### VS Code
Update your `.vscode/settings.json`:

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

#### PyCharm
1. Set Python interpreter to `.venv/bin/python`
2. Enable Ruff as external tool
3. Configure Ruff for formatting and linting

### 5. CI/CD Updates

If you have CI/CD pipelines, update them:

```yaml
# GitHub Actions example
- name: Set up Python
  uses: actions/setup-python@v4
  with:
    python-version: '3.9'

- name: Install uv
  uses: astral-sh/setup-uv@v1

- name: Install dependencies
  run: uv sync --dev

- name: Run linting
  run: uv run ruff check .

- name: Run formatting check
  run: uv run ruff format --check .

- name: Run tests
  run: uv run pytest
```

## Benefits of the New Setup

### 🚀 Performance
- **uv**: 10-100x faster than pip
- **Ruff**: 10-100x faster than the tools it replaces
- **Parallel execution**: Pre-commit hooks run in parallel

### 🛠️ Developer Experience
- **Single configuration**: Everything in `pyproject.toml`
- **Automatic formatting**: Pre-commit hooks ensure consistent code
- **Better error messages**: Ruff provides clearer feedback
- **Convenient commands**: Makefile with common tasks

### 🔧 Maintainability
- **Fewer tools**: Ruff replaces 4+ tools
- **Consistent configuration**: All settings in one place
- **Automatic updates**: Pre-commit hooks can auto-update

## Troubleshooting

### Common Issues

1. **"uv not found"**
   ```bash
   # Install uv first
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **"Virtual environment not found"**
   ```bash
   # Recreate the environment
   rm -rf .venv/
   uv sync --dev
   ```

3. **"Pre-commit hooks failing"**
   ```bash
   # Run hooks manually to see errors
   uv run pre-commit run --all-files
   ```

4. **"Import errors after migration"**
   ```bash
   # Ensure you're using the new environment
   source .venv/bin/activate
   # or use uv run for commands
   uv run python your_script.py
   ```

### Rollback (if needed)

If you need to rollback to the old setup:

```bash
# Restore requirements.txt
cp requirements.txt.backup requirements.txt

# Remove new files
rm pyproject.toml .pre-commit-config.yaml Makefile setup-dev.sh DEVELOPMENT.md

# Recreate old environment
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Getting Help

- **uv documentation**: https://docs.astral.sh/uv/
- **Ruff documentation**: https://docs.astral.sh/ruff/
- **Pre-commit documentation**: https://pre-commit.com/
- **Project development guide**: [DEVELOPMENT.md](DEVELOPMENT.md)

## Migration Checklist

- [ ] Install uv
- [ ] Run `./setup-dev.sh`
- [ ] Update IDE configuration
- [ ] Test new commands (`make help`)
- [ ] Run code quality checks (`make all-checks`)
- [ ] Update CI/CD pipelines (if applicable)
- [ ] Update team documentation
- [ ] Remove old virtual environment
- [ ] Celebrate the improved developer experience! 🎉
