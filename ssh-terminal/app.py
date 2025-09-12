"""
Simple FastAPI application with SSH Terminal WebSocket support
This is a minimal implementation to get you started
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import asyncio
import logging
import json
from pathlib import Path

# Import the terminal manager we created
from terminal_manager import terminal_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="Nexus SSH Terminal", version="0.1.0")

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "ssh-terminal"}

# Serve the terminal HTML page
@app.get("/", response_class=HTMLResponse)
async def get_terminal_page():
    # Get the directory where app.py is located
    app_dir = Path(__file__).parent
    html_path = app_dir / "terminal.html"
    
    # Also check current working directory as fallback
    if not html_path.exists():
        html_path = Path("terminal.html")
    
    if html_path.exists():
        # Use UTF-8 encoding to avoid Unicode errors
        with open(html_path, 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())
    else:
        # Provide helpful debug info
        return HTMLResponse(content=f"""
        <html>
            <body>
                <h1>Terminal HTML not found</h1>
                <p>Looking for terminal.html in:</p>
                <ul>
                    <li>App directory: {app_dir}</li>
                    <li>Current directory: {Path.cwd()}</li>
                </ul>
                <p>Please ensure terminal.html is in one of these locations.</p>
                <p>Files in app directory:</p>
                <ul>
                    {"".join(f"<li>{f.name}</li>" for f in app_dir.iterdir() if f.is_file())}
                </ul>
            </body>
        </html>
        """)

# WebSocket endpoint for terminal
@app.websocket("/ws/terminal")
async def websocket_terminal(websocket: WebSocket):
    """
    WebSocket endpoint for terminal communication
    
    Protocol:
    - Client sends: {"type": "connect", "host": "...", "port": 22, "username": "...", "password": "..."}
    - Client sends: {"type": "input", "data": "..."}
    - Client sends: {"type": "resize", "cols": 80, "rows": 24}
    - Server sends: {"type": "output", "data": "..."}
    - Server sends: {"type": "connected", "session_id": "..."}
    - Server sends: {"type": "error", "message": "..."}
    """
    await websocket.accept()
    current_session = None
    
    try:
        while True:
            # Receive message from client
            message = await websocket.receive_text()
            data = json.loads(message)
            
            msg_type = data.get('type')
            
            if msg_type == 'connect':
                # Create new SSH session
                try:
                    session_id = await terminal_manager.create_session(
                        host=data['host'],
                        port=data.get('port', 22),
                        username=data['username'],
                        password=data.get('password'),
                        key_path=data.get('key_path')
                    )
                    
                    current_session = terminal_manager.get_session(session_id)
                    if current_session:
                        current_session.websocket = websocket
                        
                    await websocket.send_text(json.dumps({
                        'type': 'connected',
                        'session_id': session_id
                    }))
                    
                    logger.info(f"WebSocket connected to SSH session {session_id}")
                    
                except Exception as e:
                    logger.error(f"Failed to create SSH session: {e}")
                    await websocket.send_text(json.dumps({
                        'type': 'error',
                        'message': f'Failed to connect: {str(e)}'
                    }))
                    
            elif msg_type == 'input':
                # Send input to SSH session
                if current_session:
                    await current_session.send_input(data['data'])
                else:
                    await websocket.send_text(json.dumps({
                        'type': 'error',
                        'message': 'No active session'
                    }))
                    
            elif msg_type == 'resize':
                # Resize terminal
                if current_session:
                    await current_session.resize(
                        cols=data.get('cols', 80),
                        rows=data.get('rows', 24)
                    )
                    
            elif msg_type == 'reconnect':
                # Reconnect to existing session
                session_id = data.get('session_id')
                if session_id:
                    current_session = terminal_manager.get_session(session_id)
                    if current_session:
                        current_session.websocket = websocket
                        await websocket.send_text(json.dumps({
                            'type': 'reconnected',
                            'session_id': session_id
                        }))
                    else:
                        await websocket.send_text(json.dumps({
                            'type': 'error',
                            'message': 'Session not found'
                        }))
                        
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_text(json.dumps({
                'type': 'error',
                'message': str(e)
            }))
        except:
            pass
    finally:
        # Clean up
        if current_session:
            current_session.websocket = None
            # Don't close SSH session on WebSocket disconnect - allow reconnection

if __name__ == "__main__":
    # Run the application
    uvicorn.run(
        "app:app",  # Use import string instead of app object
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=True  # Enable auto-reload during development
    )