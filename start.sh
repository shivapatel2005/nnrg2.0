#!/bin/bash

# ╔══════════════════════════════════════════════════════════════╗
# ║           NNRG AI Platform — Unified Launcher               ║
# ║  Starts: Agent Backend (8000) + KnowledgeBot (8001) + UI   ║
# ╚══════════════════════════════════════════════════════════════╝

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log()  { echo -e "${CYAN}[NNRG]${NC} $1"; }
ok()   { echo -e "${GREEN}[✔]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✘]${NC} $1"; }

echo ""
echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${CYAN}║       NNRG AI Platform — Starting Up...         ║${NC}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════╝${NC}"
echo ""

cleanup() {
    echo ""
    warn "Shutting down all services..."
    kill $(jobs -p) 2>/dev/null || true
    wait 2>/dev/null || true
    ok "All services stopped. Goodbye!"
}
trap cleanup EXIT INT TERM

# ════════════════════════════════════════════════════════════════
# 1. Prompt for API keys and auto-create .env files
# ════════════════════════════════════════════════════════════════
log "Setting up API keys..."

# --- Agent Backend .env ---
AGENT_ENV="$ROOT_DIR/agent-backend/.env"
if [ ! -f "$AGENT_ENV" ]; then
    echo ""
    echo -e "${YELLOW}Enter your GROQ API key (free at https://console.groq.com/keys):${NC}"
    read -r -p "  GROQ_API_KEY: " GROQ_KEY
    cat > "$AGENT_ENV" << EOF
GROQ_API_KEY=${GROQ_KEY}
GROQ_MODEL=llama-3.3-70b-versatile
NNRG_BASE_URL=https://nnrg.edu.in/
MAX_PAGES_PER_QUERY=6
MAX_CHARS_PER_DOC=6000
CHROMA_DB_PATH=./chroma_db
UPLOAD_DIR=./uploads
PORT=8000
FRONTEND_URL=http://localhost:5173
EOF
    ok "Created agent-backend/.env"
else
    ok "agent-backend/.env already exists — skipping"
fi

# --- KnowledgeBot Backend .env ---
KB_ENV="$ROOT_DIR/knowledgebot-backend/.env"
if [ ! -f "$KB_ENV" ]; then
    echo ""
    echo -e "${YELLOW}Enter your GEMINI API key (free at https://aistudio.google.com/apikey):${NC}"
    read -r -p "  GEMINI_API_KEY: " GEMINI_KEY
    cat > "$KB_ENV" << EOF
GEMINI_API_KEY=${GEMINI_KEY}
EOF
    ok "Created knowledgebot-backend/.env"
else
    ok "knowledgebot-backend/.env already exists — skipping"
fi

echo ""

# ════════════════════════════════════════════════════════════════
# 2. Agent Backend (FastAPI — port 8000)
# ════════════════════════════════════════════════════════════════
log "Setting up Agent Backend (port 8000)..."
cd "$ROOT_DIR/agent-backend"

if [ ! -d "venv" ]; then
    log "Creating Python virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate
log "Installing agent-backend dependencies..."
pip install -q -r requirements.txt
log "Starting Agent Backend on http://localhost:8000 ..."
uvicorn app:app --host 0.0.0.0 --port 8000 --reload &
AGENT_PID=$!
ok "Agent Backend started (PID $AGENT_PID)"
deactivate

# ════════════════════════════════════════════════════════════════
# 3. KnowledgeBot Backend (FastAPI — port 8001)
# ════════════════════════════════════════════════════════════════
log "Setting up KnowledgeBot Backend (port 8001)..."
cd "$ROOT_DIR/knowledgebot-backend"

if [ ! -d "venv" ]; then
    log "Creating Python virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate
log "Installing knowledgebot-backend dependencies..."
pip install -q -r requirements.txt
log "Starting KnowledgeBot Backend on http://localhost:8001 ..."
uvicorn app:app --host 0.0.0.0 --port 8001 --reload &
KB_PID=$!
ok "KnowledgeBot Backend started (PID $KB_PID)"
deactivate

# ════════════════════════════════════════════════════════════════
# 4. Frontend (React/Vite — port 5173)
# ════════════════════════════════════════════════════════════════
log "Setting up Frontend..."
cd "$ROOT_DIR/frontend"

if [ ! -d "node_modules" ]; then
    log "Installing npm dependencies (this may take a minute)..."
    npm install --silent
fi

log "Starting Frontend on http://localhost:5173 ..."
npm run dev -- --host &
FE_PID=$!
ok "Frontend started (PID $FE_PID)"

# ════════════════════════════════════════════════════════════════
# 5. All ready
# ════════════════════════════════════════════════════════════════
echo ""
echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${GREEN}║              All Services Running!              ║${NC}"
echo -e "${BOLD}${GREEN}╠══════════════════════════════════════════════════╣${NC}"
echo -e "${BOLD}${GREEN}║  🌐 Frontend       → http://localhost:5173      ║${NC}"
echo -e "${BOLD}${GREEN}║  🤖 Agent API      → http://localhost:8000      ║${NC}"
echo -e "${BOLD}${GREEN}║  📚 KnowledgeBot   → http://localhost:8001      ║${NC}"
echo -e "${BOLD}${GREEN}╠══════════════════════════════════════════════════╣${NC}"
echo -e "${BOLD}${GREEN}║  Press Ctrl+C to stop all services              ║${NC}"
echo -e "${BOLD}${GREEN}╚══════════════════════════════════════════════════╝${NC}"
echo ""

wait -n 2>/dev/null || wait
