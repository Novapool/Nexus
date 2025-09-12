# Nexus - AI-Powered SSH Terminal Management System

## Project Overview
Nexus is an AI-powered SSH terminal management tool that combines live terminal access with intelligent AI assistance. Users can manage multiple servers through both direct SSH terminal access and natural language commands processed by a local AI model.

## 🎯 Core Vision
Transform server management from manual command execution to AI-assisted administration with:
- Live SSH terminal access with full interactivity
- AI chat interface for natural language server management
- Intelligent command generation with safety validation
- Context-aware server information collection
- Secure local deployment with Docker

---

## 📊 CURRENT PROJECT STATUS

### ✅ **Phase 1: SSH Terminal Foundation - COMPLETE (95%)**

**Live SSH Terminal - FULLY FUNCTIONAL**
- ✅ FastAPI backend with WebSocket support (`app.py`)
- ✅ Real-time SSH terminal with xterm.js (`terminal.html`)
- ✅ Full SSH session management (`terminal_manager.py`)
- ✅ AsyncSSH integration with PTY support
- ✅ WebSocket protocol for terminal I/O
- ✅ Connection management with reconnection support
- ✅ Professional UI with status indicators
- ✅ Terminal resizing and copy/paste functionality
- ✅ Error handling and connection status display

**Technical Stack - ESTABLISHED**
- ✅ FastAPI backend with WebSocket endpoints
- ✅ AsyncSSH for SSH connections
- ✅ xterm.js for terminal emulation
- ✅ WebSocket communication protocol
- ✅ Clean HTML/CSS/JS interface (ready for framework migration)

---

## 🚧 **Phase 2: AI Chat Integration - IN PROGRESS (0%)**

### **2.1 Frontend Framework Migration**
**Target: Svelte + FastAPI Integration**
- 🔄 Convert current HTML/CSS/JS to Svelte components
- 🔄 Create responsive layout: Terminal (left) + AI Chat (right)
- 🔄 Implement collapsible panels
- 🔄 Maintain existing terminal functionality
- 🔄 Add state management for multi-server support

### **2.2 AI Chat Interface**
**Target: Natural Language Server Management**
- 🔄 Chat UI component with message history
- 🔄 WebSocket endpoint for AI communication (`/ws/ai`)
- 🔄 Integration with Ollama (gpt-oss:20b)
- 🔄 Message parsing and command generation
- 🔄 Context-aware responses with server information

### **2.3 Backend AI Integration**
**Target: Shared FastAPI Backend**
- 🔄 AI service integration (`ai_manager.py`)
- 🔄 Ollama client setup and configuration
- 🔄 Command generation and safety validation
- 🔄 Server context collection and caching
- 🔄 WebSocket handler for AI chat

---

## 🎯 **Phase 3: Advanced Features - PLANNED (0%)**

### **3.1 Server Management**
- 🔄 Multiple server support with dropdown selection
- 🔄 Server credentials storage (local/secure)
- 🔄 Connection profiles and quick connect
- 🔄 Server status monitoring

### **3.2 AI Context System**
- 🔄 Automatic server information collection
  - Hardware specs (CPU, RAM, disk)
  - Running services and processes
  - System logs (recent activities)
  - Configuration files (on-demand)
- 🔄 Context caching and refresh strategies
- 🔄 Smart information gathering based on AI requests

### **3.3 Security & Safety**
- 🔄 Multi-level safety system (PARANOID/SAFE/CAUTIOUS/NORMAL/PERMISSIVE)
- 🔄 Command whitelisting/blacklisting
- 🔄 User confirmation prompts for dangerous operations
- 🔄 Audit logging for all AI-generated commands
- 🔄 Rollback capability for reversible operations

### **3.4 Documentation Integration**
- 🔄 PDF document parsing and indexing
- 🔄 User documentation upload interface
- 🔄 AI context enhancement with custom docs
- 🔄 Search and reference capabilities

---

## 🚀 **Phase 4: Production & Packaging - PLANNED (0%)**

### **4.1 Docker Deployment**
- 🔄 Frontend build integration (Svelte → static files)
- 🔄 Single container: FastAPI + built Svelte app
- 🔄 Docker Compose setup with Ollama service
- 🔄 Volume mounts for persistent data
- 🔄 Environment configuration

### **4.2 Application Polish**
- 🔄 Error handling and user feedback
- 🔄 Loading states and progress indicators
- 🔄 Keyboard shortcuts and accessibility
- 🔄 Theme support (dark/light mode)
- 🔄 Settings and preferences management

### **4.3 Installation & Distribution**
- 🔄 Docker Compose deployment files
- 🔄 Installation documentation
- 🔄 Cross-platform compatibility (Windows/Linux)
- 🔄 Auto-update mechanism
- 🔄 Backup and restore functionality

---

## 🏗️ **Technical Architecture**

### **Current Architecture (Working)**
```
Frontend (HTML/CSS/JS)
    ↓ WebSocket: /ws/terminal
FastAPI Backend
    ↓ AsyncSSH
SSH Servers
```

### **Target Architecture (Phase 2+)**
```
Svelte Frontend
    ├── WebSocket: /ws/terminal → SSH Terminal
    └── WebSocket: /ws/ai → AI Chat
            ↓
FastAPI Backend
    ├── SSH Manager (existing)
    ├── AI Manager (new)
    └── Context Manager (new)
            ↓
    ├── SSH Servers
    └── Ollama (gpt-oss:20b)
```

### **Deployment Architecture (Phase 4)**
```
Docker Compose
├── nexus-app (FastAPI + Svelte static files)
├── ollama (AI service)
└── volumes (data persistence)
```

---

## 📅 **Development Timeline**

### **Immediate (2-3 weeks) - Phase 2.1**
1. **Week 1**: Svelte setup and basic layout conversion
   - Initialize Svelte project structure
   - Convert existing terminal HTML to Svelte components
   - Implement responsive split-panel layout

2. **Week 2**: AI chat interface and backend setup
   - Create chat UI components and message handling
   - Set up Ollama integration and AI WebSocket endpoint
   - Implement basic AI command generation

3. **Week 3**: Integration and testing
   - Connect AI chat with terminal execution
   - Add server context collection
   - Testing and bug fixes

### **Short-term (1-2 months) - Phase 2.2-2.3**
- Complete AI integration with context awareness
- Multi-server support and management
- Basic security and safety features
- Documentation integration system

### **Medium-term (2-3 months) - Phase 3**
- Advanced security features
- Performance optimization
- Enhanced UI/UX features
- Comprehensive testing

### **Long-term (3-4 months) - Phase 4**
- Docker packaging and deployment
- Cross-platform compatibility
- Documentation and user guides
- Production readiness

---

## 🎯 **Success Metrics**

### **Technical Goals**
- ✅ Sub-1 second SSH terminal response time (achieved)
- 🔄 Sub-3 second AI chat response time
- 🔄 Support for 5+ simultaneous SSH connections
- 🔄 99% uptime for local services
- 🔄 Memory usage under 512MB (excluding AI model)

### **User Experience Goals**
- ✅ Professional terminal interface (achieved)
- 🔄 Intuitive AI chat integration
- 🔄 Reduce complex server tasks from minutes to seconds
- 🔄 Zero-configuration setup with Docker
- 🔄 Responsive design for different screen sizes

---

## 🔧 **Development Setup**

### **Current Working Setup**
```bash
# Install dependencies
pip install -r requirements.txt

# Run the SSH terminal (currently working)
cd ssh-terminal
python app.py

# Access at http://localhost:8000
```

### **Next Phase Setup (Svelte Integration)**
```bash
# Frontend (Svelte)
npm create svelte@latest frontend
cd frontend
npm install
npm run dev

# Backend (FastAPI)
cd backend
pip install -r requirements.txt
python app.py

# Eventually: Single Docker deployment
docker-compose up
```

---

## 🚨 **Immediate Next Steps**

### **This Week**
1. **Set up Svelte project structure**
   - Initialize Svelte app in `/frontend` directory
   - Configure build process to output static files
   - Set up development proxy to FastAPI backend

2. **Convert terminal interface to Svelte**
   - Create Terminal.svelte component
   - Port existing WebSocket logic
   - Maintain all current functionality

3. **Design AI chat layout**
   - Create ChatPanel.svelte component
   - Implement split-panel layout with terminal
   - Add collapsible panel functionality

### **Next Week**
1. **AI Backend Integration**
   - Set up Ollama client in FastAPI
   - Create `/ws/ai` WebSocket endpoint
   - Implement basic AI chat functionality

2. **Connect AI to Terminal**
   - Command generation from AI responses
   - Execute commands in active SSH session
   - Display results in both terminal and chat

---

## 📝 **Key Decisions Made**

1. **Frontend Framework**: Svelte (lightweight, fast, good learning curve)
2. **Architecture**: Shared FastAPI backend with separate WebSocket endpoints
3. **AI Provider**: Ollama with gpt-oss:20b (local, privacy-focused)
4. **Deployment**: Docker Compose (single-command setup)
5. **UI Layout**: Terminal left, AI chat right, collapsible panels
6. **Target Platforms**: Windows and Linux
7. **Security Model**: Multi-level safety with user confirmation

---

## 🎉 **Project Strengths**

- ✅ **Solid Foundation**: Working SSH terminal with professional UI
- ✅ **Modern Tech Stack**: FastAPI, WebSocket, AsyncSSH, xterm.js
- ✅ **Clean Architecture**: Extensible design for AI integration
- ✅ **Local Deployment**: Privacy-focused, no cloud dependencies
- ✅ **Real-world Utility**: Solves actual server management pain points

The project has a excellent foundation with the working SSH terminal. The next phase focuses on AI integration while maintaining the quality and reliability of the existing terminal functionality.