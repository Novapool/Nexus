# Docker Setup Guide for Nexus

This guide will help you deploy Nexus using Docker. Perfect for home users and easy deployment!

## What You'll Get

- **One-command deployment** of the entire Nexus application
- **Automatic updates** - just rebuild the containers
- **Isolated environment** - won't interfere with your system
- **Easy port configuration** - run on any port you want

---

## Prerequisites

### 1. Install Docker

**Linux:**
```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER  # Add yourself to docker group
# Log out and back in for group changes to take effect
```

**macOS:**
- Download [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop/)
- Install and run Docker Desktop

**Windows:**
- Download [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/)
- Enable WSL2 if prompted
- Install and run Docker Desktop

**Verify installation:**
```bash
docker --version
docker-compose --version
```

### 2. Install Ollama (AI Model Host)

Ollama will run on your computer (not in Docker) to handle AI requests.

**Linux:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

**macOS/Windows:**
- Download from [Ollama.com](https://ollama.com/)
- Install and run the application

**Verify Ollama is running:**
```bash
ollama --version
curl http://localhost:11434  # Should return "Ollama is running"
```

### 3. Download an AI Model

Download the recommended AI model (this will take a few minutes, ~12GB):

```bash
ollama pull gpt-oss:20b
```

**Alternative lighter models:**
```bash
# Faster but less capable
ollama pull llama3.1:8b    # ~4.7GB
ollama pull mistral:7b     # ~4.1GB
```

**Check installed models:**
```bash
ollama list
```

---

## Quick Start

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd nexus
```

### 2. Configure Environment (Optional)

Copy the example environment file and customize if needed:

```bash
cp .env.example .env
```

Edit `.env` to change ports or AI model:
```bash
nano .env  # or use your preferred editor
```

**Default settings work for most users!**

### 3. Start Nexus

```bash
docker-compose up -d
```

This single command will:
- Build the backend Docker image
- Build the frontend Docker image
- Start both containers
- Set up networking between them
- Map ports to your host

**First run takes 2-5 minutes** to build everything.

### 4. Access Nexus

Open your browser to:
```
http://localhost:3000
```

🎉 **You're done!** You should see the Nexus login screen.

---

## Common Commands

### View Running Containers
```bash
docker-compose ps
```

### View Logs
```bash
# All services
docker-compose logs -f

# Just backend
docker-compose logs -f backend

# Just frontend
docker-compose logs -f frontend
```

### Stop Nexus
```bash
docker-compose down
```

### Restart Nexus
```bash
docker-compose restart
```

### Update Nexus (after pulling new code)
```bash
git pull
docker-compose down
docker-compose up -d --build
```

### Complete Cleanup (removes everything)
```bash
docker-compose down -v
docker system prune -a  # Warning: removes all unused Docker data
```

---

## Configuration

### Changing Ports

Edit `.env` file:
```bash
FRONTEND_PORT=8080  # Access UI at http://localhost:8080
BACKEND_PORT=8000   # Usually don't need to change
```

Then restart:
```bash
docker-compose down
docker-compose up -d
```

### Changing AI Model

1. Pull the model on your host:
```bash
ollama pull llama3.1:8b
```

2. Edit `.env`:
```bash
AI_MODEL=llama3.1:8b
```

3. Restart backend:
```bash
docker-compose restart backend
```

### Using Ollama on Another Computer

If Ollama runs on a different machine in your network:

Edit `.env`:
```bash
OLLAMA_HOST=192.168.1.100  # IP of machine running Ollama
OLLAMA_PORT=11434
```

---

## Troubleshooting

### "Cannot connect to Ollama"

**Check Ollama is running:**
```bash
curl http://localhost:11434
```

**Check Docker can reach host:**
```bash
docker-compose exec backend curl http://host.docker.internal:11434
```

**Solution if above fails (Linux only):**
```bash
# Find your host IP
ip addr show docker0 | grep inet

# Edit .env
OLLAMA_HOST=172.17.0.1  # Use the IP from above
```

### "Port already in use"

Change the port in `.env`:
```bash
FRONTEND_PORT=3001  # Use a different port
```

### "Backend is unhealthy"

Check backend logs:
```bash
docker-compose logs backend
```

Common issues:
- Missing Python dependencies (rebuild: `docker-compose up -d --build`)
- Can't connect to Ollama (see above)

### "Frontend shows blank page"

1. Check if backend is running:
```bash
docker-compose ps
curl http://localhost:8000/health
```

2. Rebuild frontend:
```bash
docker-compose up -d --build frontend
```

### Checking Ollama Connection

From inside the backend container:
```bash
docker-compose exec backend python -c "from ollama import AsyncClient; import asyncio; client = AsyncClient(host='http://host.docker.internal:11434'); print(asyncio.run(client.list()))"
```

---

## Advanced Usage

### Development Mode

For development with hot reload, use volume mounts:

```bash
# Already configured! Just run:
docker-compose up
```

Changes to Python files will auto-reload the backend.

For frontend development, it's better to run locally:
```bash
# Terminal 1: Backend in Docker
docker-compose up backend

# Terminal 2: Frontend locally
cd frontend
npm install
npm run dev
```

### GPU Support for Ollama (Future)

If you want to run Ollama in Docker with GPU support:

1. Install [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)
2. Use `docker-compose.gpu.yml` (coming soon)

### Building for Production

```bash
# Build images without starting
docker-compose build

# Tag and push to registry
docker tag nexus-backend:latest your-registry/nexus-backend:v1.0
docker push your-registry/nexus-backend:v1.0
```

---

## Architecture Overview

```
Your Computer
├── Ollama (Port 11434)
│   └── AI Models (~12GB)
└── Docker
    ├── Backend Container (Python/FastAPI)
    │   ├── Port 8000
    │   └── Connects to host.docker.internal:11434 → Your Ollama
    └── Frontend Container (Nginx)
        ├── Port 3000 (mapped from 80)
        ├── Serves built Svelte app
        └── Proxies /ws and /api to backend
```

---

## Security Considerations

### For Home Use:
- Default setup is fine for `localhost` access
- Don't expose port 3000 to the internet without HTTPS

### For Production:
- Use environment variables for secrets (not `.env` file)
- Enable HTTPS (add reverse proxy like Traefik/Caddy)
- Limit SSH server access
- Use Docker secrets for sensitive data
- Run behind a firewall

---

## Getting Help

**Check logs first:**
```bash
docker-compose logs -f
```

**Check service health:**
```bash
docker-compose ps
curl http://localhost:3000
curl http://localhost:8000/health
```

**Report issues:**
- [GitHub Issues](https://github.com/yourusername/nexus/issues)
- Include logs from `docker-compose logs`
- Include your OS and Docker version

---

## What's Next?

- ✅ You have Nexus running!
- 📚 See [README.md](../README.md) for usage instructions
- 🔧 See [DEVELOPMENT.md](./DEVELOPMENT.md) for contributing
- 🤖 Configure AI models for your needs

**Enjoy managing your servers with AI assistance!**
