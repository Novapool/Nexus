# Nexus Helper Scripts

These scripts make managing your Nexus Docker deployment easier.

## Available Scripts

### `start.sh` - Start Nexus
Starts all Nexus services using Docker Compose.

**Usage:**
```bash
./scripts/start.sh
```

**What it does:**
- Checks if Docker and Ollama are installed and running
- Creates `.env` from `.env.example` if missing
- Starts all Docker containers
- Shows service status and access URLs

---

### `stop.sh` - Stop Nexus
Stops all running Nexus containers.

**Usage:**
```bash
./scripts/stop.sh
```

**What it does:**
- Gracefully stops all containers
- Preserves data volumes

---

### `update.sh` - Update Nexus
Pulls latest code and rebuilds containers.

**Usage:**
```bash
./scripts/update.sh
```

**What it does:**
- Pulls latest code from git
- Stops existing containers
- Rebuilds Docker images
- Starts updated containers

---

### `logs.sh` - View Logs
Shows logs from Nexus services.

**Usage:**
```bash
# All services
./scripts/logs.sh

# Specific service
./scripts/logs.sh backend
./scripts/logs.sh frontend
```

**What it does:**
- Streams logs in real-time
- Press Ctrl+C to exit

---

### `status.sh` - System Status
Shows comprehensive status of all services.

**Usage:**
```bash
./scripts/status.sh
```

**What it does:**
- Shows Docker container status
- Checks Ollama availability and lists models
- Tests endpoint health (frontend, backend)
- Displays resource usage (CPU, memory)

---

## Quick Reference

```bash
# First time setup
./scripts/start.sh

# Daily use
./scripts/stop.sh          # Stop services
./scripts/start.sh         # Start services
./scripts/logs.sh          # View logs
./scripts/status.sh        # Check health

# Updates
./scripts/update.sh        # Get latest version

# Troubleshooting
./scripts/logs.sh backend  # Check backend logs
./scripts/status.sh        # Check what's running
```

---

## Manual Docker Commands

If you prefer using Docker Compose directly:

```bash
# Start
docker-compose up -d

# Stop
docker-compose down

# Logs
docker-compose logs -f

# Status
docker-compose ps

# Rebuild
docker-compose up -d --build

# Complete cleanup
docker-compose down -v
```

---

## Troubleshooting

**Script won't run:**
```bash
chmod +x scripts/*.sh  # Make scripts executable
```

**Permission denied:**
```bash
sudo usermod -aG docker $USER  # Add yourself to docker group
# Log out and back in
```

**Ollama not found:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull gpt-oss:20b
```

---

For more help, see [docs/DOCKER_SETUP.md](../docs/DOCKER_SETUP.md)
