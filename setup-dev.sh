#!/bin/bash
set -e

# Modern Python development setup script for bench-finder
# This script sets up the development environment using uv and modern tooling

echo "🚀 Setting up bench-finder development environment..."

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "❌ uv is not installed. Please install it first:"
    echo "   curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo "   or visit: https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
fi

# Check if pre-commit is available
if ! command -v pre-commit &> /dev/null; then
    echo "📦 Installing pre-commit..."
    uv tool install pre-commit
fi

# Install the project in development mode with all dependencies
echo "📦 Installing project dependencies..."
uv sync --dev

# Install pre-commit hooks
echo "🔧 Setting up pre-commit hooks..."
uv run pre-commit install

# Run initial checks
echo "🔍 Running initial code quality checks..."
uv run ruff check --fix .
uv run ruff format .

echo "✅ Development environment setup complete!"
echo ""
echo "Available commands:"
echo "  uv run ruff check .          # Run linting"
echo "  uv run ruff format .         # Format code"
echo "  uv run ruff check --fix .    # Run linting with auto-fix"
echo "  uv run pytest               # Run tests"
echo "  uv run pre-commit run --all-files  # Run all pre-commit hooks"
echo "  uv run bench-finder --help  # Run the main CLI"
echo ""
echo "To activate the virtual environment:"
echo "  source .venv/bin/activate"
echo ""
echo "Happy coding! 🎉"
