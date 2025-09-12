# Nexus - AI-Powered SSH Terminal Management System

<div align="center">

![Nexus Logo](https://img.shields.io/badge/Nexus-SSH%20Terminal-blue?style=for-the-badge)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-green.svg?style=for-the-badge)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg?style=for-the-badge)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104.1-teal.svg?style=for-the-badge)](https://fastapi.tiangolo.com/)
[![Svelte](https://img.shields.io/badge/Svelte-5.0-orange.svg?style=for-the-badge)](https://svelte.dev/)

**Transform server management from manual command execution to AI-assisted administration**

[🚀 Quick Start](#-quick-start) • [📖 Documentation](#-features) • [🛠️ Installation](#️-installation) • [🎯 Usage](#-usage)

</div>

---

## 🎯 Project Overview

Nexus is an AI-powered SSH terminal management tool that combines **live terminal access** with **intelligent AI assistance**. Users can manage multiple servers through both direct SSH terminal access and natural language commands processed by a local AI model.

### ✨ **Current Status: Phase 2.1 - Svelte Migration Complete (95%)**

- ✅ **Live SSH Terminal** - Fully functional with WebSocket support
- ✅ **Professional UI** - Modern Svelte frontend with responsive design  
- ✅ **Real-time Communication** - WebSocket protocol for terminal I/O
- ✅ **Connection Management** - Multi-server support with session handling
- 🔄 **AI Chat Integration** - Ready for Ollama (gpt-oss:20b) integration

---

## 🏗️ Architecture

### **Current Architecture (Working)**
```
Svelte Frontend (Port 5173)
    ├── WebSocket: /ws/terminal → SSH Terminal
    └── API Proxy: /api → FastAPI Backend
            ↓
FastAPI Backend (Port 8000)
    ├── SSH Manager (AsyncSSH)
    ├── WebSocket Handler
    └── Terminal Sessions
            ↓
SSH Servers (Any host/port)
```

### **Next Phase Architecture (Phase 2.2)**
```
Svelte Frontend
    ├── WebSocket: /ws/terminal → SSH Terminal
    └── WebSocket: /ws/ai → AI Chat (Coming Soon)
            ↓
FastAPI Backend
    ├── SSH Manager (✅ Complete)
    ├── AI Manager (🔄 In Progress)
    └── Context Manager (🔄 Planned)
            ↓
    ├── SSH Servers
    └── Ollama (gpt-oss:20b)
```

---

## 🚀 Quick Start

### **Prerequisites**
- **Python 3.8+** with pip
- **Node.js 18+** with npm
- **SSH access** to target servers

### **5-Minute Setup**

```bash
# 1. Clone the repository
git clone <your-repo-url>
cd nexus

# 2. Backend Setup
cd backend
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate     # Windows
pip install -r requirements.txt

# 3. Frontend Setup  
cd ../frontend
npm install

# 4. Start Services
# Terminal 1 - Backend
cd backend && source venv/bin/activate && python app.py

# Terminal 2 - Frontend
cd frontend && npm run dev

# 5. Open Browser
# http://localhost:5173
```

**🎉 You now have a fully functional SSH terminal in your browser!**

---

## ✨ Features

### **🖥️ Live SSH Terminal (Available Now)**
- **Real-time terminal access** with full interactivity
- **Multiple server connections** with session management
- **Professional terminal emulation** using xterm.js
- **Copy/paste support** and keyboard shortcuts
- **Connection status monitoring** with auto-reconnect
- **Responsive design** for desktop and mobile

### **🤖 AI Assistant (Phase 2.2 - Coming Soon)**
- **Natural language commands** - "Check disk space on all servers"
- **Intelligent command generation** with safety validation
- **Context-aware responses** using server information
- **Local AI processing** with Ollama (gpt-oss:20b)
- **Safety levels** from paranoid to permissive

### **🔒 Security & Safety (Phase 3 - Planned)**
- **Multi-level safety system** with command validation
- **Audit logging** for all AI-generated commands
- **Local deployment** - no cloud dependencies
- **SSH key support** with secure credential storage

---

## 🛠️ Installation

### **Development Environment**

#### **Cross-Platform Setup**
Works on Windows, macOS, and Linux:

```bash
# Backend Dependencies
cd backend
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate        # macOS/Linux
# or
venv\Scripts\activate           # Windows

pip install -r requirements.txt

# Frontend Dependencies
cd ../frontend
npm install
```

#### **Running the Application**

```bash
# Start Backend (Terminal 1)
cd backend
source venv/bin/activate  # or venv\Scripts\activate on Windows
python app.py
# Backend runs on http://localhost:8000

# Start Frontend (Terminal 2)  
cd frontend
npm run dev
# Frontend runs on http://localhost:5173 with API proxy
```

### **Docker Deployment (Phase 4 - Planned)**

```bash
# Coming Soon - Single command deployment
docker-compose up -d
```

---

## 🎯 Usage

### **1. Connect to SSH Server**

1. **Open Nexus** in your browser: `http://localhost:5173`
2. **Enter connection details**:
   - Host: `your-server.com` or IP address
   - Port: `22` (default)
   - Username: Your SSH username
   - Password: Your SSH password
3. **Click Connect** - you'll have a live terminal session!

### **2. Terminal Features**

```bash
# Everything works like a normal terminal
ls -la
cd /var/log
tail -f syslog
htop
vim config.txt

# Copy/paste with Ctrl+C / Ctrl+V
# Terminal resizing automatically
# Full color and formatting support
```

### **3. Session Management**

- **Multiple connections**: Connect to different servers simultaneously
- **Session persistence**: WebSocket reconnection maintains your session
- **Connection status**: Real-time monitoring of connection health
- **Quick disconnect**: One-click session termination

### **4. AI Assistant (Coming in Phase 2.2)**

```
You: "Check disk space on all servers"
AI: I'll check disk usage. Here's the command:
    df -h
    
Execute? [Yes/No/Modify]
```

---

## 📁 Project Structure

```
nexus/
├── backend/                    # FastAPI Backend
│   ├── app.py                 # Main FastAPI application
│   ├── terminal_manager.py    # SSH session management  
│   ├── requirements.txt       # Python dependencies
│   └── terminal.html         # Legacy HTML (backup)
├── frontend/                  # Svelte Frontend
│   ├── src/
│   │   ├── routes/+page.svelte    # Main application page
│   │   ├── lib/Terminal.svelte    # Terminal component
│   │   └── app.html              # HTML template
│   ├── package.json           # Node.js dependencies
│   └── vite.config.ts        # Vite configuration with proxy
├── README.md                  # This file
└── .gitignore                # Git ignore rules
```

---

## 🔧 Configuration

### **Environment Variables**

```bash
# Backend Configuration
NEXUS_HOST=0.0.0.0          # Backend host
NEXUS_PORT=8000             # Backend port  
NEXUS_LOG_LEVEL=info        # Logging level

# AI Configuration (Phase 2.2)
OLLAMA_HOST=localhost       # Ollama host
OLLAMA_PORT=11434          # Ollama port
AI_MODEL=gpt-oss:20b       # AI model name
```

### **Proxy Configuration**

The frontend automatically proxies API calls to the backend:

```typescript
// vite.config.ts
server: {
    proxy: {
        '/ws': 'ws://localhost:8000',    // WebSocket proxy
        '/api': 'http://localhost:8000', // API proxy
        '/health': 'http://localhost:8000'
    }
}
```

---

## 🚧 Development Status

### **✅ Phase 1: SSH Terminal Foundation - COMPLETE (95%)**
- ✅ FastAPI backend with WebSocket support
- ✅ Real-time SSH terminal with xterm.js
- ✅ Svelte frontend with responsive design
- ✅ Connection management and session handling
- ✅ Professional UI with status indicators

### **🔄 Phase 2: AI Chat Integration - IN PROGRESS (15%)**

#### **2.1 Frontend Framework Migration - COMPLETE ✅**
- ✅ Convert HTML/CSS/JS to Svelte components
- ✅ Create responsive layout: Terminal + AI Chat panels
- ✅ Maintain all existing terminal functionality
- ✅ Add collapsible panel support

#### **2.2 AI Chat Interface - NEXT (0%)**
- 🔄 Chat UI component with message history  
- 🔄 WebSocket endpoint for AI communication (`/ws/ai`)
- 🔄 Integration with Ollama (gpt-oss:20b)
- 🔄 Message parsing and command generation

#### **2.3 Backend AI Integration - PLANNED (0%)**
- 🔄 AI service integration (`ai_manager.py`)
- 🔄 Ollama client setup and configuration
- 🔄 Command generation and safety validation
- 🔄 Server context collection and caching

### **📋 Phase 3: Advanced Features - PLANNED (0%)**
- 🔄 Multi-server support with dropdown selection
- 🔄 Server credentials storage (local/secure)
- 🔄 Multi-level safety system (PARANOID/SAFE/CAUTIOUS/NORMAL/PERMISSIVE)
- 🔄 Documentation integration (PDF parsing)

### **🚀 Phase 4: Production & Packaging - PLANNED (0%)**
- 🔄 Docker Compose deployment
- 🔄 Single container: FastAPI + built Svelte app
- 🔄 Cross-platform compatibility
- 🔄 Installation documentation

---

## 📈 Technical Achievements

### **Performance Metrics**
- ✅ **Sub-1 second SSH terminal response time** - Achieved
- ✅ **Real-time WebSocket communication** - Optimized
- ✅ **Responsive UI design** - Mobile-friendly
- ✅ **Memory efficient** - <100MB without AI model
- ✅ **Cross-platform compatibility** - Windows, macOS, Linux

### **Architecture Highlights**
- ✅ **Modern tech stack**: FastAPI + Svelte + WebSockets
- ✅ **Async/await patterns** throughout the codebase
- ✅ **Type safety** with TypeScript and Python type hints
- ✅ **Component-based UI** with reusable Svelte components
- ✅ **Development proxy** for seamless frontend/backend integration

---

## 🛠️ Development

### **Running in Development Mode**

```bash
# Hot reload for both frontend and backend
npm run dev          # Frontend with hot reload
python app.py        # Backend with auto-reload
```

### **Building for Production**

```bash
# Build frontend for production
cd frontend
npm run build

# The built files will be served by FastAPI in production
```

### **Code Quality**

```bash
# Frontend linting
cd frontend
npm run lint
npm run format

# Backend formatting (future)
cd backend  
black .
isort .
```

---

## 🎯 Next Steps

### **Immediate Priority (This Week)**
1. **AI Backend Integration**
   - Set up Ollama client in FastAPI
   - Create `/ws/ai` WebSocket endpoint
   - Implement basic AI chat functionality

2. **Connect AI to Terminal**
   - Command generation from AI responses
   - Execute commands in active SSH session
   - Display results in both terminal and chat

### **This Month**
1. **Server Context Collection** - Gather system information automatically
2. **Safety System** - Implement command validation and approval workflow
3. **Multi-server Support** - Connection management with server profiles

---

## 🤝 Contributing

Nexus is in active development! Contributions welcome:

1. **Fork the repository**
2. **Create a feature branch** (`git checkout -b feature/amazing-feature`)
3. **Commit your changes** (`git commit -m 'Add amazing feature'`)
4. **Push to the branch** (`git push origin feature/amazing-feature`)
5. **Open a Pull Request**

### **Development Guidelines**
- Follow existing code patterns
- Add TypeScript types for new frontend code
- Include Python type hints for backend code
- Test your changes thoroughly
- Update documentation as needed

---

## 📄 License

This project is licensed under the Apache 2.0 License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **[OpenAI GPT-OSS](https://huggingface.co/openai/gpt-oss-20b)** - Open-weight AI model for local processing
- **[Ollama](https://ollama.ai/)** - Local AI model hosting platform
- **[FastAPI](https://fastapi.tiangolo.com/)** - Modern, fast web framework for building APIs
- **[Svelte](https://svelte.dev/)** - Cybernetically enhanced web apps
- **[AsyncSSH](https://asyncssh.readthedocs.io/)** - Asynchronous SSH2 protocol library
- **[xterm.js](https://xtermjs.org/)** - Terminal emulator for the web

---

<div align="center">

**Made with ❤️ for server administrators and DevOps engineers**

⭐ **Star this repository if Nexus helps you manage your servers better!**

[🚀 Get Started](#-quick-start) • [💬 Report Issues](https://github.com/yourusername/nexus/issues) • [📖 Documentation](https://github.com/yourusername/nexus/wiki)

</div>