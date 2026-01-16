#!/bin/bash

# ============================================
# Confluence Q&A - Development Runner
# ============================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
FRONTEND_DIST="$FRONTEND_DIR/dist"

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}   Confluence Q&A - Development Server${NC}"
echo -e "${BLUE}============================================${NC}"
echo

# Check for .env file
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    echo -e "${RED}[ERROR]${NC} .env file not found!"
    echo -e "Please create a .env file from .env.example:"
    echo -e "  ${YELLOW}cp .env.example .env${NC}"
    echo -e "Then edit .env with your configuration."
    exit 1
fi

echo -e "${GREEN}[OK]${NC} .env file found"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}[ERROR]${NC} Python 3 is not installed"
    exit 1
fi

echo -e "${GREEN}[OK]${NC} Python 3 found: $(python3 --version)"

# Check Node.js
if ! command -v node &> /dev/null; then
    echo -e "${RED}[ERROR]${NC} Node.js is not installed"
    exit 1
fi

echo -e "${GREEN}[OK]${NC} Node.js found: $(node --version)"

# Check/Create Python virtual environment
if [ ! -d "$PROJECT_ROOT/.venv" ]; then
    echo -e "${YELLOW}[INFO]${NC} Creating Python virtual environment..."
    python3 -m venv "$PROJECT_ROOT/.venv"
fi

# Activate virtual environment
source "$PROJECT_ROOT/.venv/bin/activate"
echo -e "${GREEN}[OK]${NC} Virtual environment activated"

# Install Python dependencies
echo -e "${YELLOW}[INFO]${NC} Installing Python dependencies..."
pip install -q -r "$PROJECT_ROOT/requirements.txt"
echo -e "${GREEN}[OK]${NC} Python dependencies installed"

# Check if frontend needs to be built
BUILD_FRONTEND=false

if [ ! -d "$FRONTEND_DIST" ]; then
    echo -e "${YELLOW}[INFO]${NC} Frontend dist not found, will build..."
    BUILD_FRONTEND=true
elif [ "$1" == "--build" ] || [ "$1" == "-b" ]; then
    echo -e "${YELLOW}[INFO]${NC} Force rebuild requested..."
    BUILD_FRONTEND=true
fi

if [ "$BUILD_FRONTEND" = true ]; then
    echo -e "${YELLOW}[INFO]${NC} Installing frontend dependencies..."
    cd "$FRONTEND_DIR"
    npm install --silent
    echo -e "${GREEN}[OK]${NC} Frontend dependencies installed"

    echo -e "${YELLOW}[INFO]${NC} Building frontend..."
    npm run build
    echo -e "${GREEN}[OK]${NC} Frontend built successfully"
    cd "$PROJECT_ROOT"
else
    echo -e "${GREEN}[OK]${NC} Frontend dist exists"
fi

echo
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}   Starting Application${NC}"
echo -e "${BLUE}============================================${NC}"
echo
echo -e "${GREEN}Application URL:${NC} http://localhost:8000"
echo -e "${GREEN}API Docs:${NC}        http://localhost:8000/docs"
echo
echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
echo

# Start uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
