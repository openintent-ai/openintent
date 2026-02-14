.PHONY: help install install-dev server test lint format typecheck \
       setup-mcp mcp-server full-stack clean check

PYTHON ?= python3
PIP ?= pip
NPX ?= npx
PORT ?= 8000
MCP_ROLE ?= reader

help: ## Show this help message
        @echo "OpenIntent SDK — available targets:"
        @echo ""
        @grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
                awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'
        @echo ""
        @echo "Variables (override with VAR=value):"
        @echo "  PORT          Server port         (default: $(PORT))"
        @echo "  MCP_ROLE      MCP server role      (default: $(MCP_ROLE))"
        @echo "  PYTHON        Python binary        (default: $(PYTHON))"

install: ## Install SDK with server + all adapters
        $(PIP) install -e ".[server,all-adapters]"

install-dev: ## Install SDK with dev + server + all extras
        $(PIP) install -e ".[dev,server,all-adapters]"

install-all: ## Install everything including MCP dependencies
        $(PIP) install -e ".[dev,server,all-adapters]"
        $(PIP) install mcp
        npm install -g @openintentai/mcp-server

server: ## Start the OpenIntent server
        openintent-server --port $(PORT)

test: ## Run the full test suite
        $(PYTHON) -m pytest tests/ -v

test-quick: ## Run tests without slow markers
        $(PYTHON) -m pytest tests/ -v -m "not slow"

test-mcp: ## Run MCP-related tests only
        $(PYTHON) -m pytest tests/ -v -k "mcp"

lint: ## Run linter + formatter check + type checker
        ruff check openintent/
        black --check openintent/
        mypy openintent/

format: ## Auto-format code
        black openintent/ tests/
        ruff check --fix openintent/

typecheck: ## Run type checker only
        mypy openintent/

setup-mcp: ## Install MCP dependencies (Python + Node)
        @echo "Installing Python MCP SDK..."
        $(PIP) install mcp
        @echo "Installing OpenIntent MCP server (Node)..."
        npm install -g @openintentai/mcp-server
        @echo ""
        @echo "MCP setup complete. Next steps:"
        @echo "  make server      — Start the OpenIntent server"
        @echo "  make mcp-server  — Start the MCP server (in another terminal)"
        @echo "  make full-stack  — Start both together"

mcp-server: ## Start the MCP server (connects to local OpenIntent server)
        OPENINTENT_SERVER_URL=http://localhost:$(PORT) \
        OPENINTENT_API_KEY=dev-user-key \
        OPENINTENT_MCP_ROLE=$(MCP_ROLE) \
        $(NPX) -y @openintentai/mcp-server

full-stack: ## Start OpenIntent server + MCP server together
        @echo "Starting OpenIntent server on port $(PORT)..."
        @openintent-server --port $(PORT) &
        @sleep 2
        @echo "Starting MCP server (role: $(MCP_ROLE))..."
        @OPENINTENT_SERVER_URL=http://localhost:$(PORT) \
         OPENINTENT_API_KEY=dev-user-key \
         OPENINTENT_MCP_ROLE=$(MCP_ROLE) \
         $(NPX) -y @openintentai/mcp-server

check: ## Verify installation and connectivity
        @echo "Checking Python SDK..."
        @$(PYTHON) -c "import openintent; print(f'  openintent {openintent.__version__}')" 2>/dev/null || echo "  openintent: NOT INSTALLED"
        @echo "Checking MCP SDK..."
        @$(PYTHON) -c "import mcp; print('  mcp: OK')" 2>/dev/null || echo "  mcp: NOT INSTALLED (run: make setup-mcp)"
        @echo "Checking MCP server (Node)..."
        @$(NPX) -y @openintentai/mcp-server --version 2>/dev/null && echo "  mcp-server: OK" || echo "  mcp-server: NOT INSTALLED (run: make setup-mcp)"
        @echo "Checking OpenIntent server..."
        @curl -sf http://localhost:$(PORT)/api/v1/intents > /dev/null 2>&1 && echo "  server: RUNNING on port $(PORT)" || echo "  server: NOT RUNNING (run: make server)"

clean: ## Remove build artifacts and caches
        rm -rf build/ dist/ *.egg-info .pytest_cache .mypy_cache .ruff_cache
        find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
        find . -type f -name "*.pyc" -delete 2>/dev/null || true
