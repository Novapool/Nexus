"""
Simple FastAPI application with SSH Terminal WebSocket support - FIXED VERSION
This is a minimal implementation to get you started
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import asyncio
import logging
from pathlib import Path

# Import the terminal manager and AI manager we created
from terminal_manager import terminal_manager
from ai_manager import ai_manager

# Link terminal_manager to ai_manager to avoid circular imports
ai_manager.terminal_manager = terminal_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="Nexus SSH Terminal", version="0.1.0")

# Add CORS middleware for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Dev: Vite
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "ssh-terminal"}

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
    
    logger.info("WebSocket connection accepted")
    
    try:
        while True:
            # Receive message from client
            try:
                # Add timeout to prevent hanging
                data = await asyncio.wait_for(websocket.receive_json(), timeout=60.0)

                # Don't log keepalive messages to reduce noise
                if data.get('type') != 'ping':
                    logger.debug(f"Received message: {data}")
            except asyncio.TimeoutError:
                logger.debug("WebSocket receive timeout - sending keepalive")
                # Send keepalive to check if connection is still alive
                try:
                    await websocket.send_json({'type': 'keepalive'})
                except Exception as e:
                    logger.error(f"Failed to send keepalive: {e}")
                    break
                continue
            except ValueError as e:
                logger.error(f"JSON decode error: {e}")
                try:
                    await websocket.send_json({
                        'type': 'error',
                        'message': 'Invalid JSON message'
                    })
                except Exception:
                    break
                continue
            except Exception as e:
                logger.error(f"Error receiving WebSocket message: {e}")
                break
            
            msg_type = data.get('type')
            logger.debug(f"Processing message type: {msg_type}")
            
            if msg_type == 'connect':
                # Create new SSH session
                try:
                    logger.info(f"Creating SSH session to {data['host']}:{data.get('port', 22)}")
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
                        logger.info(f"Session {session_id} created and websocket attached")

                        await websocket.send_json({
                            'type': 'connected',
                            'session_id': session_id
                        })

                        logger.info(f"WebSocket connected to SSH session {session_id}")
                    else:
                        logger.error("Failed to retrieve created session")
                        await websocket.send_json({
                            'type': 'error',
                            'message': 'Failed to retrieve session'
                        })
                    
                except Exception as e:
                    logger.error(f"Failed to create SSH session: {e}", exc_info=True)
                    await websocket.send_json({
                        'type': 'error',
                        'message': f'Failed to connect: {str(e)}'
                    })
                    
            elif msg_type == 'input':
                # Send input to SSH session
                if current_session and current_session.is_connected:
                    try:
                        input_data = data.get('data', '')
                        logger.debug(f"Sending input: {repr(input_data)}")
                        await current_session.send_input(input_data)
                    except Exception as e:
                        logger.error(f"Error sending input: {e}")
                        await websocket.send_json({
                            'type': 'error',
                            'message': f'Error sending input: {str(e)}'
                        })
                else:
                    logger.warning("No active session for input")
                    await websocket.send_json({
                        'type': 'error',
                        'message': 'No active session'
                    })
                    
            elif msg_type == 'resize':
                # Resize terminal
                if current_session and current_session.is_connected:
                    try:
                        cols = data.get('cols', 80)
                        rows = data.get('rows', 24)
                        logger.debug(f"Resizing terminal to {cols}x{rows}")
                        await current_session.resize(cols, rows)
                    except Exception as e:
                        logger.error(f"Error resizing terminal: {e}")
                        
            elif msg_type == 'reconnect':
                # Reconnect to existing session
                session_id = data.get('session_id')
                if session_id:
                    current_session = terminal_manager.get_session(session_id)
                    if current_session and current_session.is_connected:
                        current_session.websocket = websocket
                        await websocket.send_json({
                            'type': 'reconnected',
                            'session_id': session_id
                        })
                        logger.info(f"Reconnected to session {session_id}")
                    else:
                        await websocket.send_json({
                            'type': 'error',
                            'message': 'Session not found or disconnected'
                        })
                        
            elif msg_type == 'ping':
                # Respond to ping with pong
                try:
                    await websocket.send_json({'type': 'pong'})
                except Exception as e:
                    logger.error(f"Failed to send pong: {e}")
                    break
                    
            elif msg_type == 'pong':
                # Client responded to our keepalive
                logger.debug("Received pong from client")
                        
            else:
                logger.warning(f"Unknown message type: {msg_type}")
                try:
                    await websocket.send_json({
                        'type': 'error',
                        'message': f'Unknown message type: {msg_type}'
                    })
                except Exception as e:
                    logger.error(f"Failed to send error message: {e}")
                    break
                        
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected normally")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        try:
            await websocket.send_json({
                'type': 'error',
                'message': str(e)
            })
        except Exception:
            pass
    finally:
        # Clean up
        if current_session:
            current_session.websocket = None
            # Don't close SSH session on WebSocket disconnect - allow reconnection
        logger.info("WebSocket connection closed")

# WebSocket endpoint for AI chat
@app.websocket("/ws/ai")
async def websocket_ai(websocket: WebSocket):
    """
    WebSocket endpoint for AI chat communication

    Protocol:
    - Client sends: {"type": "connect", "terminal_session_id": "..."}  # Optional terminal session link
    - Client sends: {"type": "message", "content": "...", "include_context": true}
    - Client sends: {"type": "disconnect"}
    - Server sends: {"type": "connected", "ai_session_id": "..."}
    - Server sends: {"type": "message_chunk", "content": "...", "done": false}
    - Server sends: {"type": "message_complete", "full_message": "..."}
    - Server sends: {"type": "command_detected", "command": "...", "safety_level": "..."}
    - Server sends: {"type": "error", "message": "..."}
    """
    await websocket.accept()
    current_ai_session = None

    logger.info("AI WebSocket connection accepted")

    try:
        while True:
            # Receive message from client
            try:
                data = await asyncio.wait_for(websocket.receive_json(), timeout=60.0)

                # Don't log ping messages to reduce noise
                if data.get('type') != 'ping':
                    logger.debug(f"Received AI message: {data}")

            except asyncio.TimeoutError:
                logger.debug("AI WebSocket receive timeout - sending keepalive")
                try:
                    await websocket.send_json({'type': 'keepalive'})
                except Exception as e:
                    logger.error(f"Failed to send keepalive: {e}")
                    break
                continue
            except ValueError as e:
                logger.error(f"JSON decode error: {e}")
                try:
                    await websocket.send_json({
                        'type': 'error',
                        'message': 'Invalid JSON message'
                    })
                except Exception:
                    break
                continue
            except Exception as e:
                logger.error(f"Error receiving AI WebSocket message: {e}")
                break

            msg_type = data.get('type')
            logger.debug(f"Processing AI message type: {msg_type}")

            if msg_type == 'connect':
                # Create new AI session
                try:
                    terminal_session_id = data.get('terminal_session_id')
                    logger.info(f"Creating AI session (terminal link: {terminal_session_id})")

                    session_id = ai_manager.create_session(
                        terminal_session_id=terminal_session_id
                    )

                    current_ai_session = ai_manager.get_session(session_id)
                    if current_ai_session:
                        current_ai_session.websocket = websocket
                        logger.info(f"AI session {session_id} created and websocket attached")

                        await websocket.send_json({
                            'type': 'connected',
                            'ai_session_id': session_id
                        })

                        logger.info(f"WebSocket connected to AI session {session_id}")
                    else:
                        logger.error("Failed to retrieve created AI session")
                        await websocket.send_json({
                            'type': 'error',
                            'message': 'Failed to create AI session'
                        })

                except Exception as e:
                    logger.error(f"Failed to create AI session: {e}", exc_info=True)
                    await websocket.send_json({
                        'type': 'error',
                        'message': f'Failed to create AI session: {str(e)}'
                    })

            elif msg_type == 'message':
                # Send message to AI
                if current_ai_session and current_ai_session.is_connected:
                    try:
                        content = data.get('content', '')
                        include_context = data.get('include_context', True)

                        logger.info(f"Processing AI message: {content[:100]}...")

                        # Send to AI (this will stream the response)
                        await current_ai_session.send_message(content, include_context)

                    except Exception as e:
                        logger.error(f"Error processing AI message: {e}", exc_info=True)
                        await websocket.send_json({
                            'type': 'error',
                            'message': f'AI error: {str(e)}'
                        })
                else:
                    logger.warning("No active AI session for message")
                    await websocket.send_json({
                        'type': 'error',
                        'message': 'No active AI session. Please connect first.'
                    })

            elif msg_type == 'disconnect':
                # Disconnect AI session
                if current_ai_session:
                    ai_manager.close_session(current_ai_session.session_id)
                    current_ai_session = None
                    logger.info("AI session disconnected by client")

            elif msg_type == 'ping':
                # Respond to ping with pong
                try:
                    await websocket.send_json({'type': 'pong'})
                except Exception as e:
                    logger.error(f"Failed to send pong: {e}")
                    break

            elif msg_type == 'pong':
                # Client responded to our keepalive
                logger.debug("Received pong from AI client")

            else:
                logger.warning(f"Unknown AI message type: {msg_type}")
                try:
                    await websocket.send_json({
                        'type': 'error',
                        'message': f'Unknown message type: {msg_type}'
                    })
                except Exception as e:
                    logger.error(f"Failed to send error message: {e}")
                    break

    except WebSocketDisconnect:
        logger.info("AI WebSocket disconnected normally")
    except Exception as e:
        logger.error(f"AI WebSocket error: {e}", exc_info=True)
        try:
            await websocket.send_json({
                'type': 'error',
                'message': str(e)
            })
        except Exception:
            pass
    finally:
        # Clean up
        if current_ai_session:
            current_ai_session.websocket = None
            # Keep AI session alive for potential reconnection
        logger.info("AI WebSocket connection closed")

if __name__ == "__main__":
    # Run the application
    uvicorn.run(
        "app:app",  # Use import string instead of app object
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=True  # Enable auto-reload during development
    )
