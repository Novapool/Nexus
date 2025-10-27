#!/bin/bash
# Nexus Update Script
# Pulls latest code and rebuilds containers

set -e

echo "🔄 Updating Nexus SSH Terminal Management System..."
echo ""

# Check if in git repository
if [ ! -d .git ]; then
    echo "❌ Error: Not in a git repository"
    echo "   Clone the repo first: git clone <repo-url>"
    exit 1
fi

# Pull latest code
echo "📥 Pulling latest code..."
git pull

# Stop existing containers
echo ""
echo "🛑 Stopping existing containers..."
docker-compose down

# Rebuild and start
echo ""
echo "🔨 Rebuilding containers..."
docker-compose up -d --build

# Wait for services
echo ""
echo "⏳ Waiting for services to start..."
sleep 5

# Show status
echo ""
echo "📊 Service Status:"
docker-compose ps

echo ""
echo "✅ Nexus has been updated!"
echo ""
echo "📍 Access at: http://localhost:3000"
echo "📖 View logs: docker-compose logs -f"
