"""
Enhanced SSH Manager with persistent shell session support
Extends existing SSH manager to support real-time terminal sessions
"""

import asyncio
import logging
import time
import uuid
from typing import Dict, Any, Optional, Tuple, AsyncIterator
from dataclasses import dataclass, field
import asyncssh
from asyncssh import SSHClientConnection, SSHClientProcess

from backend.core.ssh_manager import SSHManager, SSHConfig, CommandResult
from backend.core.exceptions import SSHConnectionError
from backend.models.schemas import SafetyLevel

logger = logging.getLogger(__name__)


@dataclass
class ShellSession:
    """Represents a persistent shell session"""
    session_id: str
    server_id: str
    process: SSHClientProcess
    working_directory: str = "/home"
    environment_vars: Dict[str, str] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    is_active: bool = True
    command_history: list = field(default_factory=list)
    
    def update_activity(self):
        """Update last activity timestamp"""
        self.last_activity = time.time()


class EnhancedSSHManager(SSHManager):
    """Extended SSH Manager with persistent shell session support"""
    
    def __init__(self):
        super().__init__()
        self._shell_sessions: Dict[str, ShellSession] = {}
        self._session_timeout = 1800  # 30 minutes
        
    async def create_shell_session(self, session_id: Optional[str] = None) -> ShellSession:
        """Create a persistent shell session"""
        if not self._connection:
            raise SSHConnectionError("No active SSH connection")
        
        if not session_id:
            session_id = str(uuid.uuid4())
        
        # If session already exists, return it
        if session_id in self._shell_sessions:
            session = self._shell_sessions[session_id]
            if session.is_active:
                session.update_activity()
                return session
            else:
                # Clean up dead session
                await self.close_shell_session(session_id)
        
        try:
            # Create interactive shell process with PTY
            process = await self._connection.create_process(
                term_type='xterm-256color',
                term_size=(80, 24),
                encoding='utf-8',
                errors='replace'
            )
            
            # Get initial working directory
            stdin = process.stdin
            stdout = process.stdout
            
            # Send command to get working directory
            stdin.write('pwd\n')
            await stdin.drain()
            
            # Read until we get the pwd output
            output = ""
            start_time = time.time()
            while time.time() - start_time < 2:
                try:
                    chunk = await asyncio.wait_for(stdout.read(1024), timeout=0.1)
                    if chunk:
                        output += chunk
                        if '\n' in output:
                            break
                except asyncio.TimeoutError:
                    break
            
            # Extract working directory from output
            lines = output.strip().split('\n')
            working_dir = "/home"
            for line in lines:
                if line and not line.startswith('$') and not line.startswith('#'):
                    working_dir = line.strip()
                    break
            
            # Create session object
            session = ShellSession(
                session_id=session_id,
                server_id=self._connection_info.hostname,
                process=process,
                working_directory=working_dir
            )
            
            self._shell_sessions[session_id] = session
            logger.info(f"Created shell session {session_id} for {self._connection_info.hostname}")
            
            return session
            
        except Exception as e:
            logger.error(f"Failed to create shell session: {e}")
            raise SSHConnectionError(f"Failed to create shell session: {str(e)}")
    
    async def execute_in_session(self, session_id: str, command: str) -> Tuple[str, str]:
        """Execute command in a persistent shell session"""
        if session_id not in self._shell_sessions:
            raise ValueError(f"Session {session_id} not found")
        
        session = self._shell_sessions[session_id]
        if not session.is_active:
            raise SSHConnectionError(f"Session {session_id} is not active")
        
        session.update_activity()
        session.command_history.append(command)
        
        try:
            process = session.process
            stdin = process.stdin
            stdout = process.stdout
            stderr = process.stderr
            
            # Clear any pending output
            await self._drain_stream(stdout, timeout=0.1)
            await self._drain_stream(stderr, timeout=0.1)
            
            # Send command with echo off to avoid duplication
            stdin.write(f"{command}\n")
            await stdin.drain()
            
            # Collect output with timeout
            output = await self._read_until_prompt(stdout, timeout=30)
            error = await self._read_stream(stderr, timeout=0.5)
            
            # Update working directory if cd command
            if command.strip().startswith('cd '):
                stdin.write('pwd\n')
                await stdin.drain()
                pwd_output = await self._read_until_prompt(stdout, timeout=2)
                if pwd_output:
                    lines = pwd_output.strip().split('\n')
                    for line in lines:
                        if line and not line.startswith('$') and not line.startswith('#'):
                            session.working_directory = line.strip()
                            break
            
            return output, error
            
        except Exception as e:
            logger.error(f"Error executing command in session {session_id}: {e}")
            session.is_active = False
            raise SSHConnectionError(f"Session command execution failed: {str(e)}")
    
    async def stream_session_output(self, session_id: str) -> AsyncIterator[str]:
        """Stream output from a shell session"""
        if session_id not in self._shell_sessions:
            raise ValueError(f"Session {session_id} not found")
        
        session = self._shell_sessions[session_id]
        if not session.is_active:
            raise SSHConnectionError(f"Session {session_id} is not active")
        
        session.update_activity()
        stdout = session.process.stdout
        
        while session.is_active:
            try:
                chunk = await asyncio.wait_for(stdout.read(1024), timeout=0.1)
                if chunk:
                    yield chunk
            except asyncio.TimeoutError:
                # No data available, continue
                await asyncio.sleep(0.01)
            except Exception as e:
                logger.error(f"Error streaming output from session {session_id}: {e}")
                session.is_active = False
                break
    
    async def send_to_session(self, session_id: str, data: str):
        """Send raw input to a shell session (for interactive use)"""
        if session_id not in self._shell_sessions:
            raise ValueError(f"Session {session_id} not found")
        
        session = self._shell_sessions[session_id]
        if not session.is_active:
            raise SSHConnectionError(f"Session {session_id} is not active")
        
        session.update_activity()
        
        try:
            stdin = session.process.stdin
            stdin.write(data)
            await stdin.drain()
        except Exception as e:
            logger.error(f"Error sending data to session {session_id}: {e}")
            session.is_active = False
            raise SSHConnectionError(f"Failed to send data to session: {str(e)}")
    
    async def resize_session_terminal(self, session_id: str, cols: int, rows: int):
        """Resize the terminal for a shell session"""
        if session_id not in self._shell_sessions:
            raise ValueError(f"Session {session_id} not found")
        
        session = self._shell_sessions[session_id]
        if not session.is_active:
            raise SSHConnectionError(f"Session {session_id} is not active")
        
        try:
            session.process.change_terminal_size(cols, rows)
            session.update_activity()
        except Exception as e:
            logger.error(f"Error resizing terminal for session {session_id}: {e}")
    
    async def close_shell_session(self, session_id: str):
        """Close a shell session"""
        if session_id in self._shell_sessions:
            session = self._shell_sessions[session_id]
            try:
                if session.process:
                    session.process.close()
                    await session.process.wait()
            except Exception as e:
                logger.error(f"Error closing session {session_id}: {e}")
            finally:
                session.is_active = False
                del self._shell_sessions[session_id]
                logger.info(f"Closed shell session {session_id}")
    
    async def cleanup_inactive_sessions(self):
        """Clean up inactive or timed-out sessions"""
        current_time = time.time()
        sessions_to_close = []
        
        for session_id, session in self._shell_sessions.items():
            # Check if session is inactive or timed out
            if not session.is_active or \
               (current_time - session.last_activity) > self._session_timeout:
                sessions_to_close.append(session_id)
        
        for session_id in sessions_to_close:
            await self.close_shell_session(session_id)
        
        if sessions_to_close:
            logger.info(f"Cleaned up {len(sessions_to_close)} inactive sessions")
    
    async def get_session_info(self, session_id: str) -> Dict[str, Any]:
        """Get information about a shell session"""
        if session_id not in self._shell_sessions:
            return None
        
        session = self._shell_sessions[session_id]
        return {
            "session_id": session.session_id,
            "server_id": session.server_id,
            "working_directory": session.working_directory,
            "environment_vars": session.environment_vars,
            "created_at": session.created_at,
            "last_activity": session.last_activity,
            "is_active": session.is_active,
            "uptime_seconds": time.time() - session.created_at,
            "command_count": len(session.command_history)
        }
    
    async def list_sessions(self) -> list:
        """List all active shell sessions"""
        return [
            await self.get_session_info(session_id)
            for session_id in self._shell_sessions
            if self._shell_sessions[session_id].is_active
        ]
    
    async def disconnect(self):
        """Disconnect and clean up all sessions"""
        # Close all shell sessions first
        session_ids = list(self._shell_sessions.keys())
        for session_id in session_ids:
            await self.close_shell_session(session_id)
        
        # Then disconnect the SSH connection
        await super().disconnect()
    
    # Helper methods
    async def _read_stream(self, stream, timeout: float = 1.0) -> str:
        """Read available data from stream with timeout"""
        output = ""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                chunk = await asyncio.wait_for(stream.read(4096), timeout=0.1)
                if chunk:
                    output += chunk
                else:
                    break
            except asyncio.TimeoutError:
                break
        
        return output
    
    async def _drain_stream(self, stream, timeout: float = 0.5):
        """Drain any pending data from stream"""
        try:
            while True:
                chunk = await asyncio.wait_for(stream.read(4096), timeout=timeout)
                if not chunk:
                    break
        except asyncio.TimeoutError:
            pass
    
    async def _read_until_prompt(self, stream, timeout: float = 5.0) -> str:
        """Read from stream until we see a shell prompt"""
        output = ""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                chunk = await asyncio.wait_for(stream.read(1024), timeout=0.5)
                if chunk:
                    output += chunk
                    # Check for common shell prompts
                    lines = output.split('\n')
                    if lines:
                        last_line = lines[-1]
                        if any(p in last_line for p in ['$', '#', '>', '➜', '→']):
                            if len(last_line) < 100:  # Reasonable prompt length
                                break
            except asyncio.TimeoutError:
                # Check if we have enough output
                if output and '\n' in output:
                    break
        
        return output


class TerminalSessionService:
    """Service to manage terminal sessions across servers"""
    
    def __init__(self):
        self._managers: Dict[str, EnhancedSSHManager] = {}
        self._cleanup_task = None
        
    async def start(self):
        """Start the terminal session service"""
        # Start periodic cleanup task
        self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
        logger.info("Terminal session service started")
    
    async def stop(self):
        """Stop the terminal session service"""
        # Cancel cleanup task
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Disconnect all managers
        for manager in self._managers.values():
            await manager.disconnect()
        
        self._managers.clear()
        logger.info("Terminal session service stopped")
    
    async def get_or_create_manager(self, server_id: str) -> EnhancedSSHManager:
        """Get or create an enhanced SSH manager for a server"""
        if server_id not in self._managers:
            self._managers[server_id] = EnhancedSSHManager()
        return self._managers[server_id]
    
    async def create_terminal_session(
        self, 
        server_id: str, 
        server_config: SSHConfig
    ) -> Dict[str, Any]:
        """Create a new terminal session for a server"""
        manager = await self.get_or_create_manager(server_id)
        
        # Connect if not already connected
        if not manager.is_connected():
            await manager.connect(server_config)
        
        # Create shell session
        session = await manager.create_shell_session()
        
        return {
            "session_id": session.session_id,
            "server_id": server_id,
            "working_directory": session.working_directory,
            "created_at": session.created_at
        }
    
    async def _periodic_cleanup(self):
        """Periodically clean up inactive sessions"""
        while True:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes
                for manager in self._managers.values():
                    await manager.cleanup_inactive_sessions()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic cleanup: {e}")


# Global terminal session service instance
terminal_service = TerminalSessionService()
