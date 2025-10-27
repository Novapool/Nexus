#!/bin/bash
# Nexus Logs Script
# Shows logs from all or specific services

SERVICE=$1

if [ -z "$SERVICE" ]; then
    echo "📜 Showing logs from all services (Ctrl+C to exit)..."
    echo ""
    docker-compose logs -f
else
    echo "📜 Showing logs from $SERVICE (Ctrl+C to exit)..."
    echo ""
    docker-compose logs -f "$SERVICE"
fi
