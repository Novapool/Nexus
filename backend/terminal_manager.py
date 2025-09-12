"""
Live SSH Terminal Manager with WebSocket support
Provides real interactive terminal sessions via WebSockets
"""

import asyncio
import asyncssh
import json
import uuid
from typing import Dict, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class SSHTerminalSession:
    """Manages a single SSH terminal session"""
    
    def __init__(self, session_id: str, host: str, port: int, username: str, password: Optional[str] = None, key_path: Optional[str] = None):
        self.session_id = session_id
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.key_path = key_path
        
        self.connection: Optional[asyncssh.SSHClientConnection] = None
        self.process: Optional[asyncssh.SSHClientProcess] = None
        self.websocket = None
        self.is_connected = False
        self.created_at = datetime.utcnow()
        
    async def connect(self):
        """Establish SSH connection and create interactive shell"""
        try:
            # Connection options
            connect_kwargs = {
                'host': self.host,
                'port': self.port,
                'username': self.username,
                'known_hosts': None,  # Disable host key checking for now
            }
            
            # Add authentication
            if self.password:
                connect_kwargs['password'] = self.password
            elif self.key_path:
                connect_kwargs['client_keys'] = [self.key_path]
            
            # Establish connection
            self.connection = await asyncssh.connect(**connect_kwargs)
            
            # Create interactive shell process with PTY
            self.process = await self.connection.create_process(
                term_type='xterm-256color',
                term_size=(80, 24),
                encoding='utf-8'
            )
            
            self.is_connected = True
            logger.info(f"SSH session {self.session_id} connected to {self.host}")
            
            # Start reading from SSH process
            asyncio.create_task(self._read_ssh_output())
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect SSH session {self.session_id}: {e}")
            self.is_connected = False
            raise
    
    async def _read_ssh_output(self):
        """Continuously read output from SSH process and send to WebSocket"""
        try:
            while self.is_connected and self.process:
                # Read data from SSH process stdout
                try:
                    data = await self.process.stdout.read(1024)
                    if not data:
                        break
                    
                    # Decode bytes to string if needed
                    if isinstance(data, bytes):
                        data = data.decode('utf-8', errors='replace')
                    
                    # Send to WebSocket if connected
                    if self.websocket:
                        await self.websocket.send_text(json.dumps({
                            'type': 'output',
                            'data': data
                        }))
                        
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error reading SSH stdout for session {self.session_id}: {e}")
                    # Try to read stderr as well
                    try:
                        stderr_data = await self.process.stderr.read(1024)
                        if stderr_data:
                            if isinstance(stderr_data, bytes):
                                stderr_data = stderr_data.decode('utf-8', errors='replace')
                            
                            if self.websocket:
                                await self.websocket.send_text(json.dumps({
                                    'type': 'output',
                                    'data': stderr_data
                                }))
                    except:
                        pass
                    break
                    
        except Exception as e:
            logger.error(f"Error in SSH output reader for session {self.session_id}: {e}")
        finally:
            await self.disconnect()
    
    async def send_input(self, data: str):
        """Send input to SSH process"""
        if self.process and self.is_connected:
            try:
                self.process.stdin.write(data)
                await self.process.stdin.drain()
            except Exception as e:
                logger.error(f"Error sending input to SSH session {self.session_id}: {e}")
                await self.disconnect()
    
    async def resize(self, cols: int, rows: int):
        """Resize terminal window"""
        if self.process and self.is_connected:
            try:
                self.process.change_terminal_size(cols, rows)
                logger.debug(f"Resized terminal for session {self.session_id} to {cols}x{rows}")
            except Exception as e:
                logger.error(f"Error resizing terminal for session {self.session_id}: {e}")
    
    async def disconnect(self):
        """Close SSH connection and cleanup"""
        self.is_connected = False
        
        if self.process:
            try:
                self.process.terminate()
                await self.process.wait()
            except:
                pass
            self.process = None
            
        if self.connection:
            self.connection.close()
            try:
                await self.connection.wait_closed()
            except:
                pass
            self.connection = None
            
        logger.info(f"SSH session {self.session_id} disconnected")


class TerminalManager:
    """Manages multiple SSH terminal sessions"""
    
    def __init__(self):
        self.sessions: Dict[str, SSHTerminalSession] = {}
        
    async def create_session(self, host: str, port: int, username: str, 
                            password: Optional[str] = None, key_path: Optional[str] = None) -> str:
        """Create a new SSH terminal session"""
        session_id = str(uuid.uuid4())
        
        session = SSHTerminalSession(
            session_id=session_id,
            host=host,
            port=port,
            username=username,
            password=password,
            key_path=key_path
        )
        
        await session.connect()
        self.sessions[session_id] = session
        
        return session_id
    
    def get_session(self, session_id: str) -> Optional[SSHTerminalSession]:
        """Get an existing session"""
        return self.sessions.get(session_id)
    
    async def close_session(self, session_id: str):
        """Close and remove a session"""
        if session_id in self.sessions:
            session = self.sessions[session_id]
            await session.disconnect()
            del self.sessions[session_id]
            logger.info(f"Removed session {session_id}")
    
    async def cleanup_inactive_sessions(self, timeout_minutes: int = 30):
        """Clean up inactive sessions"""
        current_time = datetime.utcnow()
        sessions_to_remove = []
        
        for session_id, session in self.sessions.items():
            if not session.is_connected:
                sessions_to_remove.append(session_id)
            elif (current_time - session.created_at).total_seconds() > timeout_minutes * 60:
                sessions_to_remove.append(session_id)
        
        for session_id in sessions_to_remove:
            await self.close_session(session_id)
            
        if sessions_to_remove:
            logger.info(f"Cleaned up {len(sessions_to_remove)} inactive sessions")


# Global terminal manager instance
terminal_manager = TerminalManager()