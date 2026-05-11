#!/usr/bin/env bash
set -euo pipefail

# ─── Colors ───────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
DIM='\033[2m'
BOLD='\033[1m'
RESET='\033[0m'

# ─── Helpers ──────────────────────────────────────────────────
info()  { echo -e "${CYAN}[INFO]${RESET}  $*"; }
ok()    { echo -e "${GREEN}[OK]${RESET}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
fail()  { echo -e "${RED}[FAIL]${RESET}  $*"; exit 1; }

step() {
  echo ""
  echo -e "${BOLD}── Step $1: $2 ──${RESET}"
}

usage() {
  echo -e "${BOLD}Usage:${RESET} ./run.sh [command]"
  echo ""
  echo -e "${BOLD}Commands:${RESET}"
  echo "  setup       Full setup + launch chatbot (default)"
  echo "  eval        Run full evaluation pipeline (dataset + ablation + models + report)"
  echo "  eval:quick  Run evaluation without model comparison (faster)"
  echo "  eval:qwen   Run Qwen3.5 model comparison → data/result2/ + findings/findings2/"
  echo "  hack        Launch the red-team Hacker CLI"
  echo "  test        Run Jest test suite"
  echo ""
}

# ─── Navigate to project root ────────────────────────────────
cd "$(dirname "$0")"

# ─── Parse command ────────────────────────────────────────────
COMMAND="${1:-setup}"

# ═══════════════════════════════════════════════════════════════
# SHARED: Prerequisites check
# ═══════════════════════════════════════════════════════════════

check_prerequisites() {
  step 1 "Checking prerequisites"

  if ! command -v node &>/dev/null; then
    fail "Node.js is not installed. Install it from https://nodejs.org"
  fi
  ok "Node.js $(node -v)"

  if ! command -v npm &>/dev/null; then
    fail "npm is not installed."
  fi
  ok "npm $(npm -v)"

  if ! command -v docker &>/dev/null; then
    fail "Docker is not installed. Install it from https://www.docker.com"
  fi
  ok "Docker $(docker --version | awk '{print $3}' | tr -d ',')"

  if ! docker info < /dev/null &>/dev/null; then
    fail "Docker daemon is not running. Start Docker Desktop and try again."
  fi
  ok "Docker daemon is running"
}

install_deps() {
  step 2 "Installing npm dependencies"

  if [ -d "node_modules" ] && [ -f "package-lock.json" ]; then
    info "node_modules exists, running npm ci for reproducible install..."
    npm ci --silent
  else
    info "Running npm install..."
    npm install --silent
  fi
  ok "Dependencies installed"
}

check_env() {
  step 3 "Checking environment configuration"

  if [ ! -f ".env" ]; then
    info "No .env file found — copying from .env.example"
    cp .env.example .env
    ok "Created .env from .env.example"
  else
    ok ".env file exists"
  fi
}

start_chromadb() {
  step 4 "Starting ChromaDB"

  if curl -sf http://localhost:8000/api/v2/heartbeat < /dev/null &>/dev/null; then
    ok "ChromaDB is already running"
  else
    info "Starting ChromaDB container..."
    docker compose up -d chromadb

    info "Waiting for ChromaDB to be ready..."
    retries=0
    max_retries=30
    until curl -sf http://localhost:8000/api/v2/heartbeat < /dev/null &>/dev/null; do
      retries=$((retries + 1))
      if [ "$retries" -ge "$max_retries" ]; then
        fail "ChromaDB failed to start after ${max_retries}s. Check: docker compose logs chromadb"
      fi
      sleep 1
    done
    ok "ChromaDB is ready on port 8000"
  fi
}

seed_chromadb() {
  step 5 "Seeding ChromaDB with security patterns"
  npm run seed
  ok "Security patterns seeded"
}

check_ollama() {
  local step_num="${1:-6}"
  step "$step_num" "Checking Ollama (for semantic analysis)"

  OLLAMA_MODEL="${OLLAMA_MODEL:-llama3.2:1b}"

  if command -v ollama &>/dev/null; then
    if curl -sf http://127.0.0.1:11434/api/tags < /dev/null &>/dev/null; then
      ok "Ollama is running"

      if ollama list 2>/dev/null | grep -q "${OLLAMA_MODEL%%:*}"; then
        ok "Model '${OLLAMA_MODEL}' is available"
      else
        warn "Model '${OLLAMA_MODEL}' not found. Pulling it now..."
        ollama pull "$OLLAMA_MODEL"
        ok "Model '${OLLAMA_MODEL}' pulled"
      fi
    else
      warn "Ollama is installed but not running."
      warn "Start it with: ollama serve"
      warn "The system will fall back to rule-based validation only."
    fi
  else
    warn "Ollama is not installed."
    warn "Install from https://ollama.com for semantic analysis."
    warn "The system will fall back to rule-based validation only."
  fi
}

check_eval_models() {
  info "Checking evaluation models..."
  local models=("llama3.2:1b" "llama3.2:3b" "llama3.1:8b")
  local missing=()

  for model in "${models[@]}"; do
    if ollama list 2>/dev/null | grep -q "${model%%:*}"; then
      ok "Model '${model}' available"
    else
      missing+=("$model")
      warn "Model '${model}' not found"
    fi
  done

  if [ ${#missing[@]} -gt 0 ]; then
    warn "Missing models for model comparison: ${missing[*]}"
    warn "Pull them with: ollama pull <model>"
    return 1
  fi
  return 0
}

check_qwen_models() {
  info "Checking Qwen3.5 evaluation models..."
  local models=("qwen3.5:2b" "qwen3.5:4b" "qwen3.5:9b")
  local missing=()

  for model in "${models[@]}"; do
    if ollama list 2>/dev/null | grep -i "${model}"; then
      ok "Model '${model}' available"
    else
      missing+=("$model")
      warn "Model '${model}' not found"
    fi
  done

  if [ ${#missing[@]} -gt 0 ]; then
    warn "Missing Qwen3.5 models: ${missing[*]}"
    warn "Pull them with:"
    for m in "${missing[@]}"; do
      warn "  ollama pull ${m}"
    done
    return 1
  fi
  return 0
}

# ═══════════════════════════════════════════════════════════════
# COMMAND: setup (default)
# ═══════════════════════════════════════════════════════════════

cmd_setup() {
  echo -e "${CYAN}${BOLD}"
  echo "╔══════════════════════════════════════════════════════╗"
  echo "║  LLM Prompt Injection Security System — Setup       ║"
  echo "╚══════════════════════════════════════════════════════╝"
  echo -e "${RESET}"

  check_prerequisites
  install_deps
  check_env
  start_chromadb
  seed_chromadb
  check_ollama 6

  step 7 "Running tests"
  npm test
  ok "All tests passed"

  step 8 "Launching the chatbot"
  echo ""
  echo -e "${DIM}Tip: Type 'help' for usage, 'exit' to quit.${RESET}"
  echo -e "${DIM}Tip: Try 'ls -la' (safe) or 'ignore instructions' (attack).${RESET}"
  echo ""

  exec npm start
}

# ═══════════════════════════════════════════════════════════════
# COMMAND: eval — Full evaluation pipeline
# ═══════════════════════════════════════════════════════════════

cmd_eval() {
  local skip_models="${1:-false}"

  echo -e "${CYAN}${BOLD}"
  echo "╔══════════════════════════════════════════════════════╗"
  echo "║  Evaluation Pipeline Runner                         ║"
  echo "╚══════════════════════════════════════════════════════╝"
  echo -e "${RESET}"

  check_prerequisites
  install_deps
  check_env
  start_chromadb
  seed_chromadb
  check_ollama 6

  step 7 "Building evaluation dataset"
  npm run dataset:build
  ok "Dataset built"

  step 8 "Running ablation study (5 configurations × dataset)"
  info "This may take a while depending on your hardware..."
  npm run eval:ablation
  ok "Ablation study complete"

  if [ "$skip_models" = "false" ]; then
    step 9 "Checking models for comparison"
    if check_eval_models; then
      step 10 "Running model-size comparison (3 models × dataset)"
      info "This will take a long time (each model runs full pipeline on all entries)..."
      npm run eval:models
      ok "Model comparison complete"
    else
      warn "Skipping model comparison due to missing models."
    fi

    step 11 "Generating metrics report"
  else
    step 9 "Generating metrics report (model comparison skipped)"
  fi

  npm run eval:report
  ok "Report generated"

  echo ""
  echo -e "${GREEN}${BOLD}  Evaluation complete!${RESET}"
  echo -e "${DIM}  Results: data/results/report.md${RESET}"
  echo -e "${DIM}  JSON:    data/results/report.json${RESET}"
  echo ""
}

# ═══════════════════════════════════════════════════════════════
# COMMAND: eval:qwen — Qwen3.5 model comparison experiment
# ═══════════════════════════════════════════════════════════════

cmd_eval_qwen() {
  echo -e "${CYAN}${BOLD}"
  echo "╔══════════════════════════════════════════════════════╗"
  echo "║  Qwen3.5 Model Comparison Runner                    ║"
  echo "╚══════════════════════════════════════════════════════╝"
  echo -e "${RESET}"

  check_prerequisites
  install_deps
  check_env
  start_chromadb
  seed_chromadb
  check_ollama 6

  step 7 "Checking Qwen3.5 models"
  if ! check_qwen_models; then
    fail "Cannot proceed without all three Qwen3.5 models. Pull them first."
  fi

  step 8 "Running Qwen3.5 model comparison (3 models × dataset)"
  info "This will take a while. Each model runs the full C5 pipeline on all entries..."
  npm run eval:models:qwen
  ok "Qwen3.5 model comparison complete"

  step 9 "Generating Qwen3.5 metrics report"
  npm run eval:report:qwen
  ok "Report generated"

  step 10 "Generating Qwen3.5 figures"
  npm run eval:figures:qwen
  ok "Figures generated"

  echo ""
  echo -e "${GREEN}${BOLD}  Qwen3.5 evaluation complete!${RESET}"
  echo -e "${DIM}  Results:  data/result2/report.md${RESET}"
  echo -e "${DIM}  JSON:     data/result2/report.json${RESET}"
  echo -e "${DIM}  Figures:  findings/findings2/*.png${RESET}"
  echo ""
}

# ═══════════════════════════════════════════════════════════════
# COMMAND: hack — Red-team CLI
# ═══════════════════════════════════════════════════════════════

cmd_hack() {
  echo -e "${CYAN}${BOLD}"
  echo "╔══════════════════════════════════════════════════════╗"
  echo "║  Red-Team Hacker CLI                                ║"
  echo "╚══════════════════════════════════════════════════════╝"
  echo -e "${RESET}"

  check_prerequisites
  check_ollama 1
  exec npm run hack
}

# ═══════════════════════════════════════════════════════════════
# COMMAND: test — Run tests
# ═══════════════════════════════════════════════════════════════

cmd_test() {
  echo -e "${CYAN}${BOLD}Running test suite...${RESET}"
  npm test
}

# ═══════════════════════════════════════════════════════════════
# Dispatch
# ═══════════════════════════════════════════════════════════════

case "$COMMAND" in
  setup)      cmd_setup ;;
  eval)       cmd_eval "false" ;;
  eval:quick) cmd_eval "true" ;;
  eval:qwen)  cmd_eval_qwen ;;
  hack)       cmd_hack ;;
  test)       cmd_test ;;
  help|-h|--help) usage ;;
  *)
    echo -e "${RED}Unknown command: ${COMMAND}${RESET}"
    usage
    exit 1
    ;;
esac
