"""
Live SSH Terminal Manager with WebSocket support - FIXED VERSION
Provides real interactive terminal sessions via WebSockets
"""

import asyncio
import asyncssh
import uuid
from typing import Dict, Optional
from datetime import datetime
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class SSHConnectionError(Exception):
    """Raised when SSH connection fails"""
    pass

class SSHAuthenticationError(SSHConnectionError):
    """Raised when SSH authentication fails"""
    pass

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

        # Server context information (collected after connection)
        self.server_context: Dict[str, str] = {}
        
    async def connect(self):
        """Establish SSH connection and create interactive shell"""
        try:
            # Connection options
            # Use known_hosts file for security (defaults to ~/.ssh/known_hosts)
            known_hosts_path = Path.home() / '.ssh' / 'known_hosts'

            connect_kwargs = {
                'host': self.host,
                'port': self.port,
                'username': self.username,
                'known_hosts': str(known_hosts_path) if known_hosts_path.exists() else None,
            }
            
            # Add authentication
            if self.password:
                connect_kwargs['password'] = self.password
            elif self.key_path:
                connect_kwargs['client_keys'] = [self.key_path]
            
            # Establish connection
            try:
                self.connection = await asyncssh.connect(**connect_kwargs)
            except asyncssh.PermissionDenied as e:
                raise SSHAuthenticationError("Authentication failed") from e
            except asyncssh.Error as e:
                raise SSHConnectionError(f"Connection failed: {e}") from e
            
            # Create interactive shell process with PTY
            self.process = await self.connection.create_process(
                term_type='xterm-256color',
                term_size=(80, 24),
                encoding='utf-8',  # Let AsyncSSH handle encoding automatically
                errors='replace'   # Replace invalid UTF-8 sequences
            )
            
            self.is_connected = True
            logger.info(f"SSH session {self.session_id} connected to {self.host}")
            
            # Start reading from SSH process
            self._output_task = asyncio.create_task(self._read_ssh_output())

            # Collect server context information
            asyncio.create_task(self._collect_server_context())

            return True

        except (SSHConnectionError, SSHAuthenticationError):
            self.is_connected = False
            raise
        except Exception as e:
            logger.error(f"Failed to connect SSH session {self.session_id}: {e}")
            self.is_connected = False
            raise SSHConnectionError(f"Unexpected error: {e}") from e

    async def _collect_server_context(self):
        """Collect server information for AI context"""
        try:
            # Wait a bit for shell to be ready
            await asyncio.sleep(0.5)

            # Run commands to gather system info
            commands = {
                'os': "uname -s 2>/dev/null || echo 'Unknown'",
                'kernel': "uname -r 2>/dev/null || echo 'Unknown'",
                'distro': "cat /etc/os-release 2>/dev/null | grep '^PRETTY_NAME=' | cut -d'\"' -f2 || lsb_release -ds 2>/dev/null || echo 'Unknown'",
                'arch': "uname -m 2>/dev/null || echo 'Unknown'",
                'hostname': "hostname 2>/dev/null || echo 'Unknown'",
                'shell': "echo $SHELL 2>/dev/null || echo 'Unknown'",
                'user': "whoami 2>/dev/null || echo 'Unknown'",
                'home': "echo $HOME 2>/dev/null || echo 'Unknown'"
            }

            context = {}

            for key, cmd in commands.items():
                try:
                    result = await self.connection.run(cmd, check=False, timeout=5)
                    output = result.stdout.strip() if result.stdout else 'Unknown'
                    context[key] = output
                except Exception as e:
                    logger.debug(f"Failed to collect {key}: {e}")
                    context[key] = 'Unknown'

            self.server_context = context
            logger.info(f"Server context collected for {self.session_id}: {context.get('distro', 'Unknown')}, {context.get('arch', 'Unknown')}")

        except Exception as e:
            logger.warning(f"Error collecting server context for {self.session_id}: {e}")
            self.server_context = {'error': 'Failed to collect context'}
    
    async def _read_ssh_output(self):
        """Continuously read output from SSH process and send to WebSocket"""
        try:
            while self.is_connected and self.process:
                try:
                    # Read data from SSH process stdout
                    # AsyncSSH handles encoding automatically now
                    data = await asyncio.wait_for(self.process.stdout.read(4096), timeout=1.0)

                    if not data:
                        # EOF reached
                        logger.info(f"SSH process EOF reached for session {self.session_id}")
                        break

                    # Send to WebSocket if we have data
                    if self.websocket and data:
                        try:
                            await self.websocket.send_json({
                                'type': 'output',
                                'data': data
                            })
                            logger.debug(f"Sent {len(data)} chars to WebSocket for session {self.session_id}")
                        except Exception as e:
                            logger.error(f"Error sending to WebSocket: {e}")
                            return

                except asyncio.TimeoutError:
                    # No data available - timeout is normal
                    continue
                except asyncio.CancelledError:
                    logger.info(f"Output reader cancelled for session {self.session_id}")
                    break
                except Exception as e:
                    logger.error(f"Error reading SSH stdout for session {self.session_id}: {e}")

                    # Try to read stderr as well
                    try:
                        stderr_data = await asyncio.wait_for(self.process.stderr.read(1024), timeout=0.1)
                        if stderr_data and self.websocket:
                            await self.websocket.send_json({
                                'type': 'output',
                                'data': stderr_data
                            })
                    except Exception:
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
                # Write string directly - AsyncSSH handles encoding
                self.process.stdin.write(data)
                await self.process.stdin.drain()
                logger.debug(f"Sent {len(data)} chars to SSH session {self.session_id}")
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
