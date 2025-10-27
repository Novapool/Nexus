# Docker Implementation Summary

This document summarizes the Docker implementation for Nexus.

## What Was Created

### 1. Docker Configuration Files

#### `docker-compose.yml`
- Orchestrates 2 containers: backend (FastAPI) and frontend (Nginx)
- Connects to host Ollama via `host.docker.internal`
- Configures networking, health checks, and environment variables
- Uses `.env` file for user configuration

#### `backend/Dockerfile`
- Base: Python 3.11-slim
- Installs system dependencies (gcc, libffi-dev, libssl-dev)
- Installs Python dependencies from requirements.txt
- Runs as non-root user for security
- Includes health check
- Hot-reload enabled for development

#### `frontend/Dockerfile`
- Multi-stage build (Node.js build → Nginx serve)
- Stage 1: Builds SvelteKit app
- Stage 2: Serves with Nginx
- Lightweight final image (~50MB)
- Includes health check

#### `frontend/nginx.conf`
- Serves built Svelte app
- Proxies `/ws/*` to backend for WebSocket connections
- Proxies `/api/*` to backend for API calls
- Proxies `/health` for health checks
- Configures gzip, caching, security headers

#### `.dockerignore` files
- `backend/.dockerignore`: Excludes venv, __pycache__, tests, docs
- `frontend/.dockerignore`: Excludes node_modules, build artifacts, IDE files

#### `.env.example`
- Template for user configuration
- Documents all available environment variables
- Port configuration (FRONTEND_PORT, BACKEND_PORT)
- Ollama configuration (OLLAMA_HOST, OLLAMA_PORT, AI_MODEL)
- Logging configuration

### 2. Code Changes

#### `backend/ai_manager.py`
**Changes made:**
- Added `import os` for environment variable access
- Added global configuration from environment:
  ```python
  OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'localhost')
  OLLAMA_PORT = os.getenv('OLLAMA_PORT', '11434')
  OLLAMA_BASE_URL = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}"
  AI_MODEL = os.getenv('AI_MODEL', 'gpt-oss:20b')
  ```
- Updated all `AsyncClient()` calls to use `AsyncClient(host=OLLAMA_BASE_URL)`
- AISession now uses `AI_MODEL` from environment instead of hardcoded value

**Why:**
- Allows Docker container to connect to host Ollama via `host.docker.internal`
- Makes model selection configurable without code changes
- Enables future multi-Ollama deployments (different machines)

### 3. Helper Scripts (`scripts/`)

All scripts are executable (`chmod +x`) and user-friendly:

#### `start.sh`
- Pre-flight checks (Docker, Ollama installed and running)
- Creates `.env` from template if missing
- Starts all containers
- Shows service status and access URLs

#### `stop.sh`
- Gracefully stops all containers
- Preserves data volumes

#### `update.sh`
- Pulls latest code from git
- Rebuilds containers
- Restarts services

#### `logs.sh`
- Views logs from all services or specific service
- Real-time streaming

#### `status.sh`
- Comprehensive health check
- Shows Docker container status
- Checks Ollama availability
- Tests endpoint health
- Displays resource usage

#### `scripts/README.md`
- Documentation for all helper scripts
- Quick reference guide
- Troubleshooting tips

### 4. Documentation

#### `docs/DOCKER_SETUP.md` (2KB comprehensive guide)
- Prerequisites installation (Docker, Ollama)
- Quick start guide
- Configuration options
- Common commands
- Troubleshooting section
- Architecture overview
- Security considerations

#### `README.md` (updated)
- Added Docker deployment as recommended method
- Quick start section with Docker
- Updated installation instructions
- Updated Phase 4 status (60% complete)
- Links to Docker documentation

---

## Architecture

```
Host Machine
├── Ollama (Port 11434)
│   └── Models: ~/.ollama/models/
└── Docker
    ├── nexus-backend (Container)
    │   ├── FastAPI + AsyncSSH
    │   ├── Port: 8000
    │   └── Connects to: host.docker.internal:11434
    ├── nexus-frontend (Container)
    │   ├── Nginx + Built Svelte
    │   ├── Port: 3000 (80 internally)
    │   └── Proxies to: backend:8000
    └── nexus-network (Bridge)
```

---

## Testing the Docker Setup

### 1. Prerequisites Check
```bash
# Install Docker
curl -fsSL https://get.docker.com | sh
docker --version

# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh
ollama --version

# Pull AI model
ollama pull gpt-oss:20b
```

### 2. Start Nexus
```bash
# Option A: Using helper script (recommended)
./scripts/start.sh

# Option B: Direct docker-compose
docker-compose up -d
```

### 3. Verify Services

**Check containers:**
```bash
docker-compose ps
# Should show: nexus-backend (healthy), nexus-frontend (healthy)
```

**Check logs:**
```bash
docker-compose logs backend | grep "Ollama"
# Should show: "Ollama configured: http://host.docker.internal:11434"
```

**Test endpoints:**
```bash
# Frontend
curl http://localhost:3000
# Should return HTML

# Backend health
curl http://localhost:8000/health
# Should return: {"status":"healthy","service":"ssh-terminal"}

# Backend → Ollama connection
docker-compose exec backend python -c "import os; print(os.getenv('OLLAMA_HOST'))"
# Should return: host.docker.internal
```

### 4. Test AI Chat

1. Open browser: `http://localhost:3000`
2. Connect to an SSH server
3. Toggle AI chat panel
4. Send a message: "Check disk space"
5. Verify AI response streams back

### 5. Test Model Switching
```bash
# Pull different model
ollama pull llama3.1:8b

# Update .env
echo "AI_MODEL=llama3.1:8b" >> .env

# Restart backend
docker-compose restart backend

# Verify
docker-compose logs backend | grep "Model:"
# Should show: "Model: llama3.1:8b"
```

---

## Environment Variables

All configurable via `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `FRONTEND_PORT` | 3000 | Port for web UI |
| `BACKEND_PORT` | 8000 | Port for API server |
| `OLLAMA_HOST` | host.docker.internal | Ollama hostname |
| `OLLAMA_PORT` | 11434 | Ollama port |
| `AI_MODEL` | gpt-oss:20b | AI model name |
| `LOG_LEVEL` | info | Logging level |

---

## Troubleshooting

### "Cannot connect to Ollama"

**Diagnose:**
```bash
# Test from host
curl http://localhost:11434

# Test from container
docker-compose exec backend curl http://host.docker.internal:11434
```

**Solutions:**
- **Linux:** May need to use Docker bridge IP instead of `host.docker.internal`:
  ```bash
  ip addr show docker0 | grep inet
  # Update .env: OLLAMA_HOST=172.17.0.1
  ```
- **Mac/Windows:** `host.docker.internal` should work automatically

### "Port already in use"

Edit `.env`:
```bash
FRONTEND_PORT=3001
```
Then restart: `docker-compose down && docker-compose up -d`

### "Backend unhealthy"

Check logs:
```bash
docker-compose logs backend
```

Common causes:
- Missing Python dependencies → Rebuild: `docker-compose up -d --build`
- Can't connect to Ollama → See above

---

## Production Deployment

### Current Status (Development-Ready)
✅ Multi-container architecture
✅ Environment-based configuration
✅ Health checks
✅ Volume support for future data persistence
✅ Non-root users in containers

### Future Production Improvements
- [ ] HTTPS/TLS support (add Traefik/Caddy reverse proxy)
- [ ] Docker secrets for sensitive data
- [ ] Rate limiting for AI requests
- [ ] Resource limits (CPU, memory)
- [ ] Log aggregation (ELK stack)
- [ ] Monitoring (Prometheus + Grafana)
- [ ] Backup strategy for volumes
- [ ] CI/CD pipeline (GitHub Actions)

---

## File Checklist

Created/Modified files:
- ✅ `docker-compose.yml`
- ✅ `backend/Dockerfile`
- ✅ `backend/.dockerignore`
- ✅ `frontend/Dockerfile`
- ✅ `frontend/nginx.conf`
- ✅ `frontend/.dockerignore`
- ✅ `.env.example`
- ✅ `backend/ai_manager.py` (modified for env vars)
- ✅ `docs/DOCKER_SETUP.md`
- ✅ `README.MD` (updated)
- ✅ `scripts/start.sh`
- ✅ `scripts/stop.sh`
- ✅ `scripts/update.sh`
- ✅ `scripts/logs.sh`
- ✅ `scripts/status.sh`
- ✅ `scripts/README.md`

Existing files (not modified):
- `.gitignore` (already ignores `.env`)

---

## Next Steps for User

### Immediate Testing
```bash
# 1. Install prerequisites
curl -fsSL https://ollama.com/install.sh | sh
ollama pull gpt-oss:20b

# 2. Start Nexus
./scripts/start.sh

# 3. Open browser
open http://localhost:3000
```

### Future Model Configuration

To add more model presets in the future:

1. **Update `.env.example`** with preset comments:
```bash
# Popular models:
# AI_MODEL=gpt-oss:20b      # Best quality (12GB)
# AI_MODEL=llama3.1:8b      # Fast, good quality (4.7GB)
# AI_MODEL=mistral:7b       # Balanced (4.1GB)
# AI_MODEL=codellama:13b    # Code-focused (7.4GB)
```

2. **Create model selector UI** (future Phase 3):
   - Dropdown in settings
   - Shows available models from `ollama list`
   - Downloads model if missing
   - Restarts backend with new model

3. **Agentic capabilities** (future):
   - Different system prompts per model
   - Model-specific temperature/parameters
   - Tool use configuration
   - Multi-model ensemble

---

## Success Criteria

Docker setup is successful if:
- ✅ User can run `docker-compose up -d` and access Nexus
- ✅ AI chat connects to host Ollama
- ✅ Model is switchable via `.env` file
- ✅ All services pass health checks
- ✅ Works on Linux, macOS, and Windows (WSL2)

---

**Implementation Complete! Ready for user testing.**
