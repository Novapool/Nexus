"""
Live SSH Terminal Manager with WebSocket support - FIXED VERSION
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
        self._output_task = None
        
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
                encoding=None  # Handle encoding manually to avoid issues
            )
            
            self.is_connected = True
            logger.info(f"SSH session {self.session_id} connected to {self.host}")
            
            # Start reading from SSH process
            self._output_task = asyncio.create_task(self._read_ssh_output())
            
            # Give the shell time to initialize and send initial prompt
            await asyncio.sleep(1.0)
            
            # Send a newline to trigger the shell prompt if needed
            try:
                self.process.stdin.write(b'\r')
                await self.process.stdin.drain()
                logger.debug(f"Sent initial carriage return to trigger prompt for session {self.session_id}")
            except Exception as e:
                logger.warning(f"Could not send initial prompt trigger: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect SSH session {self.session_id}: {e}")
            self.is_connected = False
            raise
    
    async def _read_ssh_output(self):
        """Continuously read output from SSH process and send to WebSocket"""
        try:
            buffer = b''
            while self.is_connected and self.process:
                try:
                    # Read data from SSH process stdout with longer timeout
                    data = await asyncio.wait_for(self.process.stdout.read(4096), timeout=1.0)
                    
                    if not data:
                        # EOF reached
                        logger.info(f"SSH process EOF reached for session {self.session_id}")
                        break
                    
                    # Add to buffer
                    buffer += data
                    
                    # Process complete lines/chunks
                    while buffer:
                        # Try to decode what we have
                        try:
                            decoded_data = buffer.decode('utf-8')
                            buffer = b''  # Clear buffer if successful
                        except UnicodeDecodeError as e:
                            # If we can't decode, try to decode up to the error point
                            if e.start > 0:
                                decoded_data = buffer[:e.start].decode('utf-8', errors='replace')
                                buffer = buffer[e.start:]
                            else:
                                # Skip the problematic byte
                                decoded_data = buffer[:1].decode('utf-8', errors='replace')
                                buffer = buffer[1:]
                        
                        # Send to WebSocket if we have data
                        if self.websocket and decoded_data:
                            try:
                                await self.websocket.send_text(json.dumps({
                                    'type': 'output',
                                    'data': decoded_data
                                }))
                                logger.debug(f"Sent {len(decoded_data)} chars to WebSocket for session {self.session_id}")
                            except Exception as e:
                                logger.error(f"Error sending to WebSocket: {e}")
                                return
                        
                        # Break if buffer is empty
                        if not buffer:
                            break
                        
                except asyncio.TimeoutError:
                    # No data available, send keepalive if needed
                    if self.websocket:
                        try:
                            await self.websocket.send_text(json.dumps({
                                'type': 'keepalive'
                            }))
                        except:
                            pass
                    continue
                except asyncio.CancelledError:
                    logger.info(f"Output reader cancelled for session {self.session_id}")
                    break
                except Exception as e:
                    logger.error(f"Error reading SSH stdout for session {self.session_id}: {e}")
                    
                    # Try to read stderr as well
                    try:
                        stderr_data = await asyncio.wait_for(self.process.stderr.read(1024), timeout=0.1)
                        if stderr_data:
                            try:
                                stderr_decoded = stderr_data.decode('utf-8', errors='replace')
                                if self.websocket:
                                    await self.websocket.send_text(json.dumps({
                                        'type': 'output',
                                        'data': stderr_decoded
                                    }))
                            except:
                                pass
                    except:
                        pass
                    break
                    
        except Exception as e:
            logger.error(f"Error in SSH output reader for session {self.session_id}: {e}")
        finally:
            logger.info(f"Output reader for session {self.session_id} stopped")
    
    async def send_input(self, data: str):
        """Send input to SSH process"""
        if self.process and self.is_connected:
            try:
                # Encode the string to bytes
                data_bytes = data.encode('utf-8')
                self.process.stdin.write(data_bytes)
                await self.process.stdin.drain()
                logger.debug(f"Sent {len(data_bytes)} bytes to SSH session {self.session_id}")
            except Exception as e:
                logger.error(f"Error sending input to SSH session {self.session_id}: {e}")
                # Don't disconnect on input error, let user retry
    
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
        
        # Cancel output reading task
        if self._output_task and not self._output_task.done():
            self._output_task.cancel()
            try:
                await self._output_task
            except asyncio.CancelledError:
                pass
        
        if self.process:
            try:
                self.process.terminate()
                # Give it time to close gracefully
                try:
                    await asyncio.wait_for(self.process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning(f"Process for session {self.session_id} did not close gracefully")
            except Exception as e:
                logger.error(f"Error closing process for session {self.session_id}: {e}")
            self.process = None
            
        if self.connection:
            try:
                self.connection.close()
                await self.connection.wait_closed()
            except Exception as e:
                logger.error(f"Error closing connection for session {self.session_id}: {e}")
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
