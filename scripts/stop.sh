#!/bin/bash
# Nexus Stop Script
# Stops Nexus Docker containers

set -e

echo "🛑 Stopping Nexus SSH Terminal Management System..."
echo ""

# Check if Docker Compose is available
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null 2>&1; then
    echo "❌ Error: Docker Compose is not installed"
    exit 1
fi

# Stop containers
docker-compose down

echo ""
echo "✅ Nexus has been stopped"
echo ""
echo "To start again: ./scripts/start.sh"
echo "To remove all data: docker-compose down -v"
