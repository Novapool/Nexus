# Nexus - AI-Powered Server Management System

<div align="center">

![Nexus Logo](https://img.shields.io/badge/Nexus-AI%20Server%20Management-blue?style=for-the-badge&logo=server)

**Transform server management from manual command execution to conversational automation**

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

</div>

## 🚀 Quick Start

Nexus allows you to manage multiple servers using natural language commands powered by AI. Instead of remembering complex SSH commands, simply tell Nexus what you want to do:

- *"Check disk space on all my servers"*
- *"Install Docker on my Ubuntu servers"*
- *"Show me which services are using the most CPU"*
- *"Update all packages on server-01"*

## ✨ Features

### 🤖 AI-Powered Command Generation
- **Natural Language Interface**: Describe what you want to do in plain English
- **Smart Command Translation**: AI converts requests to appropriate shell commands
- **Safety Validation**: Multi-level risk assessment before execution
- **Context-Aware**: Understands your server environment and generates relevant commands

### 🖥️ Server Management
- **Multi-Server Support**: Manage dozens of servers from one interface
- **Real-Time Monitoring**: Live performance metrics and health checks
- **Hardware Profiling**: Automatic detection of CPU, memory, storage, and services
- **Secure Connections**: Encrypted SSH with connection pooling

### 🌐 Web Interface
- **Modern Responsive UI**: Clean, intuitive interface accessible from any device
- **Real-Time Execution**: Watch commands execute with live output streaming
- **Server Profiles**: Detailed hardware and service information
- **Bulk Operations**: Execute commands across multiple servers simultaneously

### 🔒 Security & Safety
- **Multi-Level Safety**: PARANOID to PERMISSIVE safety modes
- **Encrypted Credentials**: Secure storage of SSH keys and passwords
- **Command Validation**: Pre-execution safety checks
- **Audit Logging**: Complete history of all operations

## 📋 Prerequisites

- **Python 3.9+**
- **Ollama** with `gpt-oss:20b` model
- **SSH access** to target servers
- **Linux/macOS/Windows** (development tested on all platforms)

## 🛠️ Installation

### Step 1: Clone the Repository

```bash
git clone https://github.com/yourusername/nexus.git
cd nexus
```

### Step 2: Install Dependencies

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Linux/macOS:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 3: Install and Configure Ollama

```bash
# Install Ollama (visit https://ollama.ai for platform-specific instructions)
curl -fsSL https://ollama.ai/install.sh | sh

# Pull the required model
ollama pull gpt-oss:20b

# Verify installation
ollama list
```

### Step 4: Configure Environment

```bash
# Copy example configuration
cp .env.example .env

# Edit configuration (optional - defaults work for most setups)
nano .env
```

**Example `.env` configuration:**

```bash
# Database
DATABASE_URL=sqlite+aiosqlite:///./nexus.db

# API Settings
API_HOST=127.0.0.1
API_PORT=8000
DEBUG=true

# Ollama Configuration
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=gpt-oss:20b

# Security
SECRET_KEY=your-secret-key-here
ENCRYPTION_KEY=your-32-byte-encryption-key-here

# Logging
LOG_LEVEL=INFO
```

### Step 5: Initialize Database

```bash
# Run database migrations
alembic upgrade head
```

### Step 6: Start the Application

```bash
# Start Nexus
python run.py
```

The application will be available at:
- **Web Interface**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

## 🚦 Usage Guide

### Adding Your First Server

1. **Open the web interface** at http://localhost:8000
2. **Click "Add Server"** in the top navigation
3. **Fill in server details**:
   - **Name**: A friendly name for your server
   - **Host**: IP address or hostname
   - **Port**: SSH port (usually 22)
   - **Username**: SSH username
   - **Authentication**: Choose password or SSH key
4. **Test connection** using the "Test Connection" button
5. **Save** the server configuration

### Executing Commands

#### Natural Language Commands
1. **Select a server** from the server list
2. **Type your request** in natural language:
   - *"Show me disk usage"*
   - *"List running Docker containers"*
   - *"Check system load"*
3. **Review the generated command** before execution
4. **Execute** and watch real-time output

#### Direct Commands
1. **Switch to "Direct Command" mode**
2. **Enter shell commands** directly
3. **Execute** with full output capture

### Server Profiling

Nexus automatically profiles your servers to understand their environment:

- **Hardware**: CPU, memory, storage, network interfaces
- **Operating System**: Distribution, version, kernel
- **Services**: Running services, Docker containers, systemd units
- **Performance**: Load average, memory usage, disk space

This information helps the AI generate more accurate and relevant commands.

### Safety Levels

Choose the appropriate safety level for your environment:

- **🔴 PARANOID**: Maximum safety, requires confirmation for any command
- **🟡 SAFE**: Conservative approach, blocks potentially dangerous commands
- **🟠 CAUTIOUS**: Balanced safety with productivity
- **🟢 NORMAL**: Standard operation mode
- **🔵 PERMISSIVE**: Minimal restrictions for experienced users

## 🔧 Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite+aiosqlite:///./nexus.db` | Database connection string |
| `API_HOST` | `127.0.0.1` | API server host |
| `API_PORT` | `8000` | API server port |
| `DEBUG` | `false` | Enable debug mode |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `gpt-oss:20b` | AI model to use |
| `SECRET_KEY` | Generated | JWT signing key |
| `ENCRYPTION_KEY` | Generated | Database encryption key |
| `LOG_LEVEL` | `INFO` | Logging level |

### Database Configuration

Nexus supports multiple database backends:

```bash
# SQLite (default - recommended for single user)
DATABASE_URL=sqlite+aiosqlite:///./nexus.db

# PostgreSQL (recommended for multi-user)
DATABASE_URL=postgresql+asyncpg://user:password@localhost/nexus

# MySQL
DATABASE_URL=mysql+aiomysql://user:password@localhost/nexus
```

### SSH Configuration

For key-based authentication, place your SSH keys in:
- **Private keys**: `~/.ssh/id_rsa`, `~/.ssh/id_ed25519`, etc.
- **Public keys**: Automatically detected
- **Custom paths**: Specify full path in server configuration

## 🐳 Docker Deployment

### Quick Start with Docker

```bash
# Build and run with Docker Compose
docker-compose up -d

# Or run manually
docker build -t nexus .
docker run -p 8000:8000 -v ./data:/app/data nexus
```

### Docker Compose Configuration

```yaml
version: '3.8'

services:
  nexus:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - ~/.ssh:/root/.ssh:ro
    environment:
      - DATABASE_URL=sqlite+aiosqlite:///./data/nexus.db
      - OLLAMA_HOST=http://ollama:11434
    depends_on:
      - ollama

  ollama:
    image: ollama/ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    command: serve

volumes:
  ollama_data:
```

## 🔍 API Reference

### Authentication

```bash
# Health check (no auth required)
curl http://localhost:8000/health

# Get server list
curl -H "Authorization: Bearer YOUR_TOKEN" \
     http://localhost:8000/api/v1/servers
```

### Server Management

```bash
# Add a server
curl -X POST http://localhost:8000/api/v1/servers \
  -H "Content-Type: application/json" \
  -d '{
    "name": "web-server-01",
    "host": "192.168.1.100",
    "port": 22,
    "username": "admin",
    "auth_type": "password",
    "password": "securepassword"
  }'

# Test server connection
curl -X POST http://localhost:8000/api/v1/servers/{id}/test-connection
```

### AI Command Generation

```bash
# Generate command from natural language
curl -X POST http://localhost:8000/api/v1/ai/generate-command \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "show disk usage",
    "server_id": "server-uuid",
    "safety_level": "SAFE"
  }'

# Execute AI-generated command
curl -X POST http://localhost:8000/api/v1/ai/execute-command \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "check system load",
    "server_id": "server-uuid"
  }'
```

### Direct Command Execution

```bash
# Execute direct command
curl -X POST http://localhost:8000/api/v1/servers/{id}/execute \
  -H "Content-Type: application/json" \
  -d '{
    "command": "df -h",
    "timeout": 30
  }'
```

## 🔧 Troubleshooting

### Common Issues

#### Ollama Connection Failed
```bash
# Check if Ollama is running
ollama list

# Start Ollama service
ollama serve

# Verify model is available
ollama show gpt-oss:20b
```

#### SSH Connection Issues
- **Verify SSH access**: Test manual SSH connection
- **Check credentials**: Ensure username/password or SSH keys are correct
- **Firewall**: Ensure port 22 (or custom SSH port) is accessible
- **Host key verification**: Add servers to `~/.ssh/known_hosts`

#### Database Migration Errors
```bash
# Reset database (WARNING: deletes all data)
rm nexus.db
alembic upgrade head

# Check migration status
alembic current
alembic history
```

#### Performance Issues
- **Increase timeout values** in server configuration
- **Use SSH key authentication** instead of passwords
- **Enable connection pooling** for frequently accessed servers
- **Monitor system resources** (CPU, memory, network)

### Debug Mode

Enable debug mode for detailed logging:

```bash
# Set environment variable
export DEBUG=true

# Or edit .env file
DEBUG=true

# Restart application
python run.py
```

### Log Files

Check application logs for detailed error information:

```bash
# View application logs
tail -f logs/nexus.log

# Check Ollama logs
ollama logs
```

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Development Setup

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
pytest

# Format code
black .
isort .

# Type checking
mypy backend/
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Documentation**: [Full documentation](docs/)
- **Issues**: [GitHub Issues](https://github.com/yourusername/nexus/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/nexus/discussions)

## 🙏 Acknowledgments

- **OpenAI GPT-OSS**: AI model for command generation
- **Ollama**: Local AI model hosting
- **FastAPI**: Modern web framework
- **AsyncSSH**: Async SSH library
- **SQLAlchemy**: Database ORM

---

<div align="center">

**Made with ❤️ for server administrators everywhere**

⭐ Star this repository if Nexus helps you manage your servers better!

</div>
