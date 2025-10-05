#!/usr/bin/env python3
"""
Production-ready startup script for the FastAPI Bench Finder server.
Provides both development and production configurations.
"""
import os
import sys
import argparse
from pathlib import Path
import uvicorn


def get_app_config():
    """Get application configuration from environment variables."""
    return {
        'host': os.getenv('HOST', '0.0.0.0'),
        'port': int(os.getenv('PORT', '8866')),
        'workers': int(os.getenv('WORKERS', '1')),
        'log_level': os.getenv('LOG_LEVEL', 'info').lower(),
        'reload': os.getenv('RELOAD', 'false').lower() == 'true',
    }


def main():
    parser = argparse.ArgumentParser(description='Start the FastAPI Bench Finder server')
    parser.add_argument(
        '--mode', 
        choices=['dev', 'prod'], 
        default='dev',
        help='Server mode: dev (development) or prod (production)'
    )
    parser.add_argument(
        '--host', 
        default=None,
        help='Host to bind to (overrides environment)'
    )
    parser.add_argument(
        '--port', 
        type=int, 
        default=None,
        help='Port to bind to (overrides environment)'
    )
    parser.add_argument(
        '--workers', 
        type=int, 
        default=None,
        help='Number of worker processes (production mode only)'
    )
    parser.add_argument(
        '--reload', 
        action='store_true',
        help='Enable auto-reload on code changes (development only)'
    )
    
    args = parser.parse_args()
    config = get_app_config()
    
    # Override config with command line arguments
    if args.host:
        config['host'] = args.host
    if args.port:
        config['port'] = args.port
    if args.workers:
        config['workers'] = args.workers
    if args.reload:
        config['reload'] = True
    
    # Ensure the FastAPI server module is importable
    current_dir = Path(__file__).parent
    if str(current_dir) not in sys.path:
        sys.path.insert(0, str(current_dir))\n    
    print(\"🚀 Starting Bench Finder FastAPI Server\")\n    print(f\"📍 Mode: {args.mode}\")\n    print(f\"🌐 URL: http://{config['host']}:{config['port']}\")\n    print(f\"📚 API Docs: http://{config['host']}:{config['port']}/docs\")\n    print(f\"🔄 Redoc: http://{config['host']}:{config['port']}/redoc\")\n    \n    if args.mode == 'dev':\n        print(\"\\n🔧 Development Configuration:\")\n        print(f\"   - Hot reload: {'✅' if config['reload'] else '❌'}\")\n        print(f\"   - Log level: {config['log_level']}\")\n        print(f\"   - Single worker process\")\n        \n        # Development server with hot reload\n        uvicorn.run(\n            \"fastapi_server:app\",\n            host=config['host'],\n            port=config['port'],\n            reload=config['reload'],\n            log_level=config['log_level'],\n            access_log=True\n        )\n        \n    else:  # production mode\n        print(\"\\n🏭 Production Configuration:\")\n        print(f\"   - Workers: {config['workers']}\")\n        print(f\"   - Log level: {config['log_level']}\")\n        print(f\"   - Hot reload: disabled\")\n        print(\"\\n⚠️  Production mode recommendations:\")\n        print(\"   - Use a reverse proxy (nginx, caddy, etc.)\")\n        print(\"   - Set up proper logging and monitoring\")\n        print(\"   - Configure environment variables for security\")\n        print(\"   - Use a process manager (systemd, supervisor, etc.)\")\n        \n        # Production server configuration\n        if config['workers'] > 1:\n            print(f\"\\n🔀 Starting {config['workers']} worker processes...\")\n            # For multiple workers, we need to use Gunicorn with uvicorn workers\n            try:\n                import gunicorn.app.wsgiapp\n                from gunicorn.app.base import BaseApplication\n                \n                class StandaloneApplication(BaseApplication):\n                    def __init__(self, app, options=None):\n                        self.options = options or {}\n                        self.application = app\n                        super().__init__()\n                    \n                    def load_config(self):\n                        config = {key: value for key, value in self.options.items()\n                                if key in self.cfg.settings and value is not None}\n                        for key, value in config.items():\n                            self.cfg.set(key.lower(), value)\n                    \n                    def load(self):\n                        return self.application\n                \n                options = {\n                    'bind': f\"{config['host']}:{config['port']}\",\n                    'workers': config['workers'],\n                    'worker_class': 'uvicorn.workers.UvicornWorker',\n                    'log_level': config['log_level'],\n                    'access_log': True,\n                    'preload_app': True,\n                }\n                \n                from fastapi_server import app\n                StandaloneApplication(app, options).run()\n                \n            except ImportError:\n                print(\"⚠️  Gunicorn not available, falling back to single uvicorn worker\")\n                uvicorn.run(\n                    \"fastapi_server:app\",\n                    host=config['host'],\n                    port=config['port'],\n                    log_level=config['log_level'],\n                    access_log=True\n                )\n        else:\n            # Single worker production server\n            uvicorn.run(\n                \"fastapi_server:app\",\n                host=config['host'],\n                port=config['port'],\n                log_level=config['log_level'],\n                access_log=True\n            )\n\n\nif __name__ == \"__main__\":\n    main()