# Docker Quick Start

One-page guide to get Nexus running with Docker.

## 🚀 First Time Setup (5 Minutes)

```bash
# 1. Install Docker (Linux)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER  # Add yourself to docker group
# Log out and back in

# 2. Install Ollama
curl -fsSL https://ollama.com/install.sh | sh
ollama pull gpt-oss:20b  # Download AI model (~12GB, takes a few minutes)

# 3. Clone and start Nexus
git clone <your-repo-url>
cd nexus
./scripts/start.sh

# 4. Open browser
# http://localhost:3000
```

**That's it!** 🎉

---

## 📋 Daily Commands

```bash
# Start Nexus
./scripts/start.sh

# Stop Nexus
./scripts/stop.sh

# View logs (live)
./scripts/logs.sh

# Check status
./scripts/status.sh

# Update to latest version
./scripts/update.sh
```

---

## ⚙️ Configuration

Edit `.env` to customize:

```bash
# Copy template (first time only)
cp .env.example .env

# Change ports
FRONTEND_PORT=3000    # Web UI port
BACKEND_PORT=8000     # API port

# Change AI model
AI_MODEL=gpt-oss:20b        # Default
# AI_MODEL=llama3.1:8b      # Faster
# AI_MODEL=mistral:7b       # Lighter

# After changes, restart:
docker-compose restart
```

---

## 🔍 Troubleshooting

### Can't connect to Ollama?

```bash
# Test Ollama
curl http://localhost:11434

# If fails, start Ollama
ollama serve

# Check logs
./scripts/logs.sh backend
```

### Port already in use?

```bash
# Edit .env
nano .env
# Change: FRONTEND_PORT=3001

# Restart
docker-compose down
docker-compose up -d
```

### See what's running?

```bash
# Quick check
docker-compose ps

# Detailed status
./scripts/status.sh

# View all logs
./scripts/logs.sh
```

---

## 🧹 Cleanup

```bash
# Stop everything
docker-compose down

# Remove all data (fresh start)
docker-compose down -v
docker system prune -a
```

---

## 📖 Full Documentation

- **Setup Guide:** [docs/DOCKER_SETUP.md](docs/DOCKER_SETUP.md)
- **Implementation Details:** [DOCKER_IMPLEMENTATION.md](DOCKER_IMPLEMENTATION.md)
- **Scripts Help:** [scripts/README.md](scripts/README.md)
- **Main README:** [README.md](README.md)

---

## 🆘 Common Issues

| Problem | Solution |
|---------|----------|
| "Docker command not found" | Install Docker: `curl -fsSL https://get.docker.com \| sh` |
| "Permission denied" | Add to docker group: `sudo usermod -aG docker $USER` |
| "Ollama not running" | Start Ollama: `ollama serve` |
| "AI not responding" | Check logs: `./scripts/logs.sh backend` |
| "Port 3000 in use" | Change port in `.env`: `FRONTEND_PORT=3001` |
| "Can't connect to SSH" | Check SSH credentials and firewall rules |

---

## 🎯 Access Points

- **Web UI:** http://localhost:3000
- **API:** http://localhost:8000
- **Health Check:** http://localhost:8000/health

---

**Happy server managing!** 🎉
