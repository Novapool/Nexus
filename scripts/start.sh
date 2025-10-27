#!/bin/bash
# Nexus Startup Script
# Starts Nexus using Docker Compose

set -e

echo "🚀 Starting Nexus SSH Terminal Management System..."
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Error: Docker is not installed"
    echo "   Install Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if Docker Compose is available
if ! command -v docker compose &> /dev/null && ! docker compose version &> /dev/null 2>&1; then
    echo "❌ Error: Docker Compose is not installed"
    echo "   Install Docker Compose: https://docs.docker.com/compose/install/"
    exit 1
fi

# Check if Ollama is running
echo "🔍 Checking Ollama status..."
if ! curl -s http://localhost:11434/api/tags &> /dev/null; then
    echo "⚠️  Warning: Ollama doesn't seem to be running on localhost:11434"
    echo "   The AI chat feature won't work without Ollama"
    echo "   Install: curl -fsSL https://ollama.com/install.sh | sh"
    echo "   Then run: ollama pull gpt-oss:20b"
    echo ""
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo "✅ Ollama is running"

    # Check if Ollama is listening on all interfaces (required for Docker)
    LISTEN_ADDR=$(ss -tlnp 2>/dev/null | grep 11434 | awk '{print $4}' | head -1)
    if echo "$LISTEN_ADDR" | grep -q "127.0.0.1:11434"; then
        echo "⚠️  Warning: Ollama is only listening on localhost (127.0.0.1)"
        echo "   Docker containers won't be able to connect"
        echo ""
        read -p "Run automatic fix? (Y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Nn]$ ]]; then
            if [ -f "./scripts/fix-ollama-docker.sh" ]; then
                ./scripts/fix-ollama-docker.sh
            else
                echo "❌ Fix script not found at ./scripts/fix-ollama-docker.sh"
                exit 1
            fi
        fi
    else
        echo "✅ Ollama is accessible from Docker"
    fi
fi

# Check for .env file, create from example if missing
if [ ! -f .env ]; then
    echo "📝 Creating .env from .env.example..."
    cp .env.example .env
    echo "   Edit .env to customize configuration"
fi

# Start Docker Compose
echo ""
echo "🐳 Starting Docker containers..."
docker compose up -d

# Wait for services to be healthy
echo ""
echo "⏳ Waiting for services to start..."
sleep 3

# Check service status
echo ""
echo "📊 Service Status:"
docker compose ps

# Show access information
echo ""
echo "✅ Nexus is starting!"
echo ""
echo "📍 Access Points:"
echo "   Web UI:     http://localhost:3000"
echo "   Backend:    http://localhost:8000"
echo "   Health:     http://localhost:8000/health"
echo ""
echo "📖 View logs:  docker compose logs -f"
echo "🛑 Stop:       docker compose down"
echo ""
echo "🎉 Happy server managing!"
