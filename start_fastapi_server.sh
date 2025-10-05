#!/bin/bash

# FastAPI Bench Finder Server Startup Script
# Provides easy commands for development and production deployment

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default configuration
DEFAULT_HOST="0.0.0.0"
DEFAULT_PORT="8866"
DEFAULT_WORKERS="1"
DEFAULT_LOG_LEVEL="info"

# Parse command line arguments
MODE="dev"
HOST=${HOST:-$DEFAULT_HOST}
PORT=${PORT:-$DEFAULT_PORT}
WORKERS=${WORKERS:-$DEFAULT_WORKERS}
LOG_LEVEL=${LOG_LEVEL:-$DEFAULT_LOG_LEVEL}
RELOAD=false

show_help() {
    echo "FastAPI Bench Finder Server"
    echo ""
    echo "Usage: $0 [OPTIONS] [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  dev      Start development server (default)"
    echo "  prod     Start production server"
    echo "  check    Check server dependencies and configuration"
    echo "  help     Show this help message"
    echo ""
    echo "Options:"
    echo "  --host HOST        Host to bind to (default: $DEFAULT_HOST)"
    echo "  --port PORT        Port to bind to (default: $DEFAULT_PORT)"
    echo "  --workers N        Number of worker processes (default: $DEFAULT_WORKERS)"
    echo "  --log-level LEVEL  Log level (default: $DEFAULT_LOG_LEVEL)"
    echo "  --reload           Enable auto-reload in dev mode"
    echo ""
    echo "Environment variables:"
    echo "  HOST, PORT, WORKERS, LOG_LEVEL, RELOAD"
    echo ""
    echo "Examples:"
    echo "  $0 dev --reload                    # Development with auto-reload"
    echo "  $0 prod --workers 4 --port 8080    # Production with 4 workers"
    echo "  HOST=localhost PORT=3000 $0 dev    # Custom host and port"
}

check_dependencies() {
    echo -e "${BLUE}🔍 Checking dependencies...${NC}"
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}❌ Python 3 is required but not installed${NC}"
        exit 1
    fi
    
    # Check required Python packages
    python3 -c "import fastapi, uvicorn, pydantic" 2>/dev/null || {
        echo -e "${RED}❌ Required Python packages not installed${NC}"
        echo -e "${YELLOW}💡 Run: pip install -r requirements.txt${NC}"
        exit 1
    }
    
    # Check if fastapi_server.py exists
    if [ ! -f "fastapi_server.py" ]; then
        echo -e "${RED}❌ fastapi_server.py not found${NC}"
        exit 1
    fi
    
    # Check database file
    if [ ! -f "*.db" ] && [ ! -f "*bench*.db" ]; then
        echo -e "${YELLOW}⚠️  No database file found - the server may not work properly${NC}"
    fi
    
    echo -e "${GREEN}✅ All dependencies check passed${NC}"
}

start_development() {
    echo -e "${GREEN}🚀 Starting Bench Finder FastAPI Server (Development)${NC}"
    echo -e "${BLUE}📍 Mode: Development${NC}"
    echo -e "${BLUE}🌐 URL: http://${HOST}:${PORT}${NC}"
    echo -e "${BLUE}📚 API Docs: http://${HOST}:${PORT}/docs${NC}"
    echo -e "${BLUE}🔄 Redoc: http://${HOST}:${PORT}/redoc${NC}"
    echo ""
    echo -e "${YELLOW}🔧 Development Configuration:${NC}"
    echo "   - Hot reload: $([ "$RELOAD" = true ] && echo '✅' || echo '❌')"
    echo "   - Log level: ${LOG_LEVEL}"
    echo "   - Single worker process"
    echo ""
    
    RELOAD_FLAG=""
    if [ "$RELOAD" = true ]; then
        RELOAD_FLAG="--reload"
    fi
    
    python3 -m uvicorn fastapi_server:app \
        --host "$HOST" \
        --port "$PORT" \
        --log-level "$LOG_LEVEL" \
        $RELOAD_FLAG
}

start_production() {
    echo -e "${GREEN}🚀 Starting Bench Finder FastAPI Server (Production)${NC}"
    echo -e "${BLUE}📍 Mode: Production${NC}"
    echo -e "${BLUE}🌐 URL: http://${HOST}:${PORT}${NC}"
    echo -e "${BLUE}📚 API Docs: http://${HOST}:${PORT}/docs${NC}"
    echo -e "${BLUE}🔄 Redoc: http://${HOST}:${PORT}/redoc${NC}"
    echo ""
    echo -e "${YELLOW}🏭 Production Configuration:${NC}"
    echo "   - Workers: ${WORKERS}"
    echo "   - Log level: ${LOG_LEVEL}"
    echo "   - Hot reload: disabled"
    echo ""
    echo -e "${YELLOW}⚠️  Production recommendations:${NC}"
    echo "   - Use a reverse proxy (nginx, caddy, etc.)"
    echo "   - Set up proper logging and monitoring"
    echo "   - Configure environment variables for security"
    echo "   - Use a process manager (systemd, supervisor, etc.)"
    echo ""
    
    if [ "$WORKERS" -gt 1 ]; then
        # Check if gunicorn is available
        if python3 -c "import gunicorn" 2>/dev/null; then
            echo -e "${BLUE}🔀 Starting ${WORKERS} worker processes with Gunicorn...${NC}"
            python3 -m gunicorn fastapi_server:app \
                -w "$WORKERS" \
                -k uvicorn.workers.UvicornWorker \
                --bind "${HOST}:${PORT}" \
                --log-level "$LOG_LEVEL" \
                --access-logfile -
        else
            echo -e "${YELLOW}⚠️  Gunicorn not available, falling back to single uvicorn worker${NC}"
            python3 -m uvicorn fastapi_server:app \
                --host "$HOST" \
                --port "$PORT" \
                --log-level "$LOG_LEVEL"
        fi
    else
        python3 -m uvicorn fastapi_server:app \
            --host "$HOST" \
            --port "$PORT" \
            --log-level "$LOG_LEVEL"
    fi
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --host)
            HOST="$2"
            shift 2
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        --workers)
            WORKERS="$2"
            shift 2
            ;;
        --log-level)
            LOG_LEVEL="$2"
            shift 2
            ;;
        --reload)
            RELOAD=true
            shift
            ;;
        dev|development)
            MODE="dev"
            shift
            ;;
        prod|production)
            MODE="prod"
            shift
            ;;
        check)
            check_dependencies
            exit 0
            ;;
        help|--help|-h)
            show_help
            exit 0
            ;;
        *)
            echo -e "${RED}❌ Unknown argument: $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

# Check dependencies before starting
check_dependencies

# Start the server
case $MODE in
    dev)
        start_development
        ;;
    prod)
        start_production
        ;;
    *)
        echo -e "${RED}❌ Unknown mode: $MODE${NC}"
        show_help
        exit 1
        ;;
esac