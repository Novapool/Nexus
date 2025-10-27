# Nexus Helper Scripts

These scripts simplify Docker Compose operations for Nexus.

## Available Scripts

### `start.sh` - Start Nexus
Starts all Nexus services using Docker Compose.

```bash
./scripts/start.sh
```

Creates `.env` from `.env.example` if missing, then starts all containers.

---

### `stop.sh` - Stop Nexus
Stops all running Nexus containers.

```bash
./scripts/stop.sh
```

---

### `update.sh` - Update Nexus
Pulls latest code and rebuilds containers.

```bash
./scripts/update.sh
```

---

### `logs.sh` - View Logs
Shows logs from Nexus services.

```bash
# All services
./scripts/logs.sh

# Specific service
./scripts/logs.sh backend
./scripts/logs.sh frontend
```

---

### `status.sh` - System Status
Shows comprehensive status of all services.

```bash
./scripts/status.sh
```

Displays Docker container status, Ollama availability, endpoint health, and resource usage.

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
```

## Direct Docker Commands

```bash
# Start
docker compose up -d

# Stop
docker compose down

# Logs
docker compose logs -f [service]

# Rebuild
docker compose up -d --build
```

## Troubleshooting

**AI chat not working?**

1. Check backend logs: `./scripts/logs.sh backend`
2. Ensure Ollama is running: `ollama list`
3. Verify .env has: `OLLAMA_HOST=host.docker.internal`

**Linux-specific:** Ollama must listen on all interfaces (0.0.0.0), not just localhost.

Create `/etc/systemd/system/ollama.service.d/override.conf`:
```ini
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
```

Then restart: `sudo systemctl daemon-reload && sudo systemctl restart ollama`

For more help, see project documentation.
