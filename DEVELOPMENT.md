# Development Guide

## FastAPI Server with Auto-Reload

The Bench Finder FastAPI server supports automatic reloading when Python files change, making development much more efficient.

### Prerequisites

Make sure you have the required dependencies installed:

```bash
# Install dependencies using uv (recommended)
uv sync --dev

# Or install uvicorn directly
uv add uvicorn[standard] fastapi
```

### Quick Start

#### Option 1: Using Make (Recommended)
```bash
# From the project root directory
make run-server
```

#### Option 2: Direct uvicorn
```bash
# From the project root directory
uv run uvicorn api.fastapi_server:app --reload --host 0.0.0.0 --port 8866
```

#### Option 3: Using the startup script
```bash
# From the project root directory
./bin/start_fastapi dev --reload
```

### Auto-Reload Configuration

The server is configured to automatically reload when any Python file changes in:
- `api/` directory
- `bench_finder/` directory
- `tools/` directory

**Excluded files:**
- `*.pyc` (compiled Python files)
- `__pycache__/` directories
- `*.log` files
- `*.tmp` files

### What Triggers a Reload

The server will automatically restart when you modify:
- Any `.py` file in the watched directories
- The main FastAPI application code
- API models and endpoints
- Business logic in the `bench_finder` package
- Utility scripts in the `tools` directory

### Development Workflow

1. Start the development server using one of the methods above
2. Make changes to your Python files
3. The server automatically detects changes and restarts
4. Your changes are immediately available at `http://localhost:8866`

### API Documentation

Once the server is running, you can access:
- **Interactive API docs**: http://localhost:8866/docs
- **ReDoc documentation**: http://localhost:8866/redoc
- **OpenAPI JSON**: http://localhost:8866/openapi.json

### Troubleshooting

If auto-reload isn't working:

1. **Check file permissions**: Ensure the files you're editing are writable
2. **Verify directory structure**: Make sure you're running from the project root
3. **Check for syntax errors**: The server won't reload if there are Python syntax errors
4. **Restart manually**: If needed, stop the server (Ctrl+C) and restart it

### Environment Variables

You can customize the server behavior with environment variables:

```bash
export HOST=0.0.0.0          # Server host (default: 0.0.0.0)
export PORT=8866             # Server port (default: 8866)
export RELOAD=true           # Enable auto-reload (default: false)
export LOG_LEVEL=info        # Log level (default: info)
```

### Production vs Development

- **Development mode**: Auto-reload enabled, single worker, detailed logging
- **Production mode**: Auto-reload disabled, multiple workers, optimized logging

Use the startup script with `--mode prod` for production deployment.
