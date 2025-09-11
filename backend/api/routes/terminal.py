"""
WebSocket route for real-time terminal sessions
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from backend.config.database import get_db
from backend.models.database import Server, TerminalSession, User
from backend.core.ssh_manager import SSHConfig
from backend.utils.crypto import decrypt_password
from backend.services.terminal_service import terminal_service
from backend.core.exceptions import SSHConnectionError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/terminal", tags=["terminal"])


class CreateTerminalSessionRequest(BaseModel):
    """Request model for creating terminal sessions"""
    server_id: str


class TerminalWebSocketManager:
    """Manages WebSocket connections for terminal sessions"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        
    async def connect(self, session_id: str, websocket: WebSocket):
        """Accept and register a new WebSocket connection"""
        await websocket.accept()
        self.active_connections[session_id] = websocket
        logger.info(f"WebSocket connected for session {session_id}")
        
    def disconnect(self, session_id: str):
        """Remove a WebSocket connection"""
        if session_id in self.active_connections:
            del self.active_connections[session_id]
            logger.info(f"WebSocket disconnected for session {session_id}")
    
    async def send_message(self, session_id: str, message: Dict[str, Any]):
        """Send a message to a specific WebSocket connection"""
        if session_id in self.active_connections:
            websocket = self.active_connections[session_id]
            await websocket.send_json(message)
    
    async def broadcast_to_session(self, session_id: str, message: Dict[str, Any]):
        """Broadcast a message to all connections for a session"""
        # In future, could support multiple connections per session
        await self.send_message(session_id, message)


# Global WebSocket manager
ws_manager = TerminalWebSocketManager()


@router.post("/sessions")
async def create_terminal_session(
    request: CreateTerminalSessionRequest,
    db: AsyncSession = Depends(get_db)
) -> JSONResponse:
    """Create a new terminal session for a server"""
    try:
        server_id = request.server_id
        
        # Get server configuration
        query = select(Server).where(Server.id == server_id)
        result = await db.execute(query)
        server = result.scalar_one_or_none()
        
        if not server:
            raise HTTPException(status_code=404, detail="Server not found")
        
        # Decrypt password
        password = None
        if server.password:
            try:
                password = decrypt_password(server.password)
            except Exception as e:
                logger.error(f"Failed to decrypt password for server {server_id}: {e}")
                raise HTTPException(status_code=500, detail="Failed to decrypt server password")
        
        # Create SSH config
        ssh_config = SSHConfig(
            hostname=server.hostname,
            username=server.username,
            port=server.port,
            password=password,
            timeout=30
        )
        
        # Create terminal session
        session_info = await terminal_service.create_terminal_session(server_id, ssh_config)
        
        # Store session in database
        terminal_session = TerminalSession(
            id=session_info["session_id"],
            session_token=session_info["session_id"],
            server_id=server_id,
            user_id="default",  # TODO: Get from auth when implemented
            working_directory=session_info["working_directory"],
            environment_vars="{}",
            is_active=True,
            connection_id=None,
            created_at=datetime.utcnow(),
            last_activity=datetime.utcnow()
        )
        
        db.add(terminal_session)
        await db.commit()
        
        return JSONResponse(content={
            "session_id": session_info["session_id"],
            "server_id": server_id,
            "working_directory": session_info["working_directory"],
            "message": "Terminal session created successfully"
        })
        
    except SSHConnectionError as e:
        logger.error(f"SSH connection error: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create terminal session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.websocket("/{session_id}/ws")
async def terminal_websocket(
    websocket: WebSocket,
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """WebSocket endpoint for terminal interaction"""
    
    # Verify session exists
    query = select(TerminalSession).where(TerminalSession.id == session_id)
    result = await db.execute(query)
    terminal_session = result.scalar_one_or_none()
    
    if not terminal_session or not terminal_session.is_active:
        await websocket.close(code=4004, reason="Session not found or inactive")
        return
    
    # Connect WebSocket
    await ws_manager.connect(session_id, websocket)
    
    # Update session connection info
    terminal_session.connection_id = session_id
    terminal_session.last_activity = datetime.utcnow()
    await db.commit()
    
    # Get the SSH manager for this server
    manager = await terminal_service.get_or_create_manager(terminal_session.server_id)
    
    # Send initial connection success message
    await websocket.send_json({
        "type": "connected",
        "session_id": session_id,
        "working_directory": terminal_session.working_directory
    })
    
    # Create tasks for bidirectional communication
    output_task = None
    
    try:
        # Start output streaming task
        async def stream_output():
            """Stream output from SSH session to WebSocket"""
            try:
                async for output in manager.stream_session_output(session_id):
                    if output:
                        await websocket.send_json({
                            "type": "output",
                            "data": output
                        })
            except Exception as e:
                logger.error(f"Error streaming output: {e}")
                await websocket.send_json({
                    "type": "error",
                    "message": f"Output stream error: {str(e)}"
                })
        
        output_task = asyncio.create_task(stream_output())
        
        # Handle input from WebSocket
        while True:
            try:
                # Receive message from WebSocket
                message = await websocket.receive_json()
                message_type = message.get("type")
                
                if message_type == "command":
                    # Execute command in session
                    command = message.get("command", "")
                    if command:
                        stdout, stderr = await manager.execute_in_session(session_id, command)
                        
                        # Send command output
                        if stdout:
                            await websocket.send_json({
                                "type": "output",
                                "data": stdout
                            })
                        
                        if stderr:
                            await websocket.send_json({
                                "type": "error",
                                "data": stderr
                            })
                        
                        # Update session activity
                        terminal_session.last_activity = datetime.utcnow()
                        
                        # Get updated session info
                        session_info = await manager.get_session_info(session_id)
                        if session_info:
                            terminal_session.working_directory = session_info["working_directory"]
                            await websocket.send_json({
                                "type": "directory_changed",
                                "working_directory": session_info["working_directory"]
                            })
                        
                        await db.commit()
                
                elif message_type == "input":
                    # Send raw input to session (for interactive commands)
                    data = message.get("data", "")
                    await manager.send_to_session(session_id, data)
                
                elif message_type == "resize":
                    # Resize terminal
                    cols = message.get("cols", 80)
                    rows = message.get("rows", 24)
                    await manager.resize_session_terminal(session_id, cols, rows)
                    
                    await websocket.send_json({
                        "type": "resized",
                        "cols": cols,
                        "rows": rows
                    })
                
                elif message_type == "ping":
                    # Respond to ping
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": datetime.utcnow().isoformat()
                    })
                
                elif message_type == "close":
                    # Close session
                    break
                
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected for session {session_id}")
                break
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON message"
                })
            except Exception as e:
                logger.error(f"Error handling WebSocket message: {e}")
                await websocket.send_json({
                    "type": "error",
                    "message": str(e)
                })
                
    finally:
        # Cancel output streaming task
        if output_task:
            output_task.cancel()
            try:
                await output_task
            except asyncio.CancelledError:
                pass
        
        # Disconnect WebSocket
        ws_manager.disconnect(session_id)
        
        # Update session status
        terminal_session.is_active = False
        terminal_session.closed_at = datetime.utcnow()
        await db.commit()
        
        # Close SSH session if configured to do so
        # (Keep it alive for reconnection within timeout period)
        # await manager.close_shell_session(session_id)


@router.get("/sessions")
async def list_terminal_sessions(
    server_id: Optional[str] = Query(None),
    active_only: bool = Query(True),
    db: AsyncSession = Depends(get_db)
) -> JSONResponse:
    """List terminal sessions"""
    try:
        query = select(TerminalSession)
        
        if server_id:
            query = query.where(TerminalSession.server_id == server_id)
        
        if active_only:
            query = query.where(TerminalSession.is_active == True)
        
        result = await db.execute(query)
        sessions = result.scalars().all()
        
        session_list = []
        for session in sessions:
            # Get real-time session info from manager if available
            manager = await terminal_service.get_or_create_manager(session.server_id)
            session_info = await manager.get_session_info(session.id)
            
            if session_info:
                session_list.append({
                    "session_id": session.id,
                    "server_id": session.server_id,
                    "working_directory": session_info["working_directory"],
                    "is_active": session_info["is_active"],
                    "created_at": session.created_at.isoformat(),
                    "last_activity": session.last_activity.isoformat(),
                    "uptime_seconds": session_info["uptime_seconds"],
                    "command_count": session_info["command_count"]
                })
            else:
                session_list.append({
                    "session_id": session.id,
                    "server_id": session.server_id,
                    "working_directory": session.working_directory,
                    "is_active": session.is_active,
                    "created_at": session.created_at.isoformat(),
                    "last_activity": session.last_activity.isoformat()
                })
        
        return JSONResponse(content={
            "sessions": session_list,
            "count": len(session_list)
        })
        
    except Exception as e:
        logger.error(f"Failed to list terminal sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/sessions/{session_id}")
async def close_terminal_session(
    session_id: str,
    db: AsyncSession = Depends(get_db)
) -> JSONResponse:
    """Close a terminal session"""
    try:
        # Get session from database
        query = select(TerminalSession).where(TerminalSession.id == session_id)
        result = await db.execute(query)
        terminal_session = result.scalar_one_or_none()
        
        if not terminal_session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Close SSH session
        manager = await terminal_service.get_or_create_manager(terminal_session.server_id)
        await manager.close_shell_session(session_id)
        
        # Update database
        terminal_session.is_active = False
        terminal_session.closed_at = datetime.utcnow()
        await db.commit()
        
        return JSONResponse(content={
            "message": "Terminal session closed successfully",
            "session_id": session_id
        })
        
    except Exception as e:
        logger.error(f"Failed to close terminal session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/reconnect")
async def reconnect_terminal_session(
    session_id: str,
    db: AsyncSession = Depends(get_db)
) -> JSONResponse:
    """Attempt to reconnect to an existing terminal session"""
    try:
        # Get session from database
        query = select(TerminalSession).where(TerminalSession.id == session_id)
        result = await db.execute(query)
        terminal_session = result.scalar_one_or_none()
        
        if not terminal_session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Check if session can be reconnected
        manager = await terminal_service.get_or_create_manager(terminal_session.server_id)
        session_info = await manager.get_session_info(session_id)
        
        if session_info and session_info["is_active"]:
            # Session is still active, update database
            terminal_session.is_active = True
            terminal_session.last_activity = datetime.utcnow()
            await db.commit()
            
            return JSONResponse(content={
                "message": "Reconnected to terminal session",
                "session_id": session_id,
                "working_directory": session_info["working_directory"],
                "uptime_seconds": session_info["uptime_seconds"]
            })
        else:
            # Session is dead, create a new one
            raise HTTPException(
                status_code=410, 
                detail="Session has expired. Please create a new session."
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reconnect terminal session: {e}")
        raise HTTPException(status_code=500, detail=str(e))
