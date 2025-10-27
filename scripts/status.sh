#!/bin/bash
# Nexus Status Script
# Shows detailed status of all services

echo "📊 Nexus System Status"
echo "====================="
echo ""

# Docker containers
echo "🐳 Docker Containers:"
docker-compose ps
echo ""

# Check Ollama
echo "🤖 Ollama Status:"
if curl -s http://localhost:11434 &> /dev/null; then
    echo "   ✅ Running on localhost:11434"
    # Try to list models
    if command -v ollama &> /dev/null; then
        echo ""
        echo "   Available models:"
        ollama list | sed 's/^/   /'
    fi
else
    echo "   ❌ Not running on localhost:11434"
fi
echo ""

# Check endpoints
echo "🌐 Endpoint Health:"
if curl -s http://localhost:3000 &> /dev/null; then
    echo "   ✅ Frontend: http://localhost:3000"
else
    echo "   ❌ Frontend: http://localhost:3000 (unreachable)"
fi

if curl -s http://localhost:8000/health &> /dev/null; then
    echo "   ✅ Backend: http://localhost:8000"
else
    echo "   ❌ Backend: http://localhost:8000 (unreachable)"
fi
echo ""

# Resource usage
echo "💾 Resource Usage:"
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" | grep nexus || echo "   No containers running"
echo ""
