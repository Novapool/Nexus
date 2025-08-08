#!/usr/bin/env python3
"""
Nexus development startup script
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import uvicorn
from backend.main import app
from backend.config.settings import get_settings


async def check_ollama():
    """Check if Ollama is running"""
    import httpx
    
    settings = get_settings()
    
    if not settings.enable_ai:
        print("✓ AI features disabled")
        return
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.ollama_base_url}/api/tags")
            if response.status_code == 200:
                models = response.json().get("models", [])
                print(f"✓ Ollama is running with {len(models)} models available")
                
                # Check if our target model is available
                model_names = [m["name"] for m in models]
                if settings.ai_model_name in model_names:
                    print(f"✓ Target model '{settings.ai_model_name}' is available")
                else:
                    print(f"⚠ Target model '{settings.ai_model_name}' not found")
                    print(f"  Available models: {', '.join(model_names)}")
                    print(f"  Run: ollama pull {settings.ai_model_name}")
            else:
                print(f"⚠ Ollama responded with status {response.status_code}")
    except Exception as e:
        print(f"⚠ Ollama not accessible: {e}")
        print("  Make sure Ollama is installed and running:")
        print("  - Install: https://ollama.ai/download")
        print(f"  - Run: ollama pull {settings.ai_model_name}")
        print("  - Start: ollama serve")


def create_directories():
    """Create necessary directories"""
    directories = [
        "data",
        "data/logs",
        "data/backups"
    ]
    
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
    
    print("✓ Created necessary directories")


def check_environment():
    """Check environment setup"""
    env_file = Path(".env")
    
    if not env_file.exists():
        print("⚠ No .env file found")
        print("  Copy .env.example to .env and configure your settings")
        
        # Create basic .env file
        with open(".env", "w") as f:
            f.write("DEBUG=true\n")
            f.write("SECRET_KEY=development-key-change-in-production\n")
        print("✓ Created basic .env file")
    else:
        print("✓ Environment file exists")


async def main():
    """Main startup function"""
    print("🚀 Starting Nexus Server Management System")
    print("=" * 50)
    
    # Setup checks
    check_environment()
    create_directories()
    await check_ollama()
    
    print("=" * 50)
    
    # Get settings
    settings = get_settings()
    
    print(f"Starting server on {settings.host}:{settings.port}")
    print(f"Debug mode: {settings.debug}")
    print(f"API docs: http://{settings.host}:{settings.port}/docs")
    print(f"Health check: http://{settings.host}:{settings.port}/health")
    print("=" * 50)
    
    # Start the server
    config = uvicorn.Config(
        app=app,
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info" if not settings.debug else "debug",
        access_log=settings.debug
    )
    
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Shutting down Nexus...")
    except Exception as e:
        print(f"❌ Failed to start: {e}")
        sys.exit(1)