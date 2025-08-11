"""
Application configuration management using Pydantic Settings
"""

from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )
    
    # Application settings
    app_name: str = "Nexus Server Management"
    debug: bool = Field(default=False, description="Enable debug mode")
    host: str = Field(default="127.0.0.1", description="Host to bind the server")
    port: int = Field(default=8000, description="Port to bind the server")
    
    # Security settings
    secret_key: str = Field(
        default="your-secret-key-change-this-in-production",
        description="Secret key for JWT tokens"
    )
    algorithm: str = Field(default="HS256", description="JWT algorithm")
    access_token_expire_minutes: int = Field(
        default=30, 
        description="Access token expiration time in minutes"
    )
    allowed_hosts: Union[List[str], str] = Field(
        default=["localhost", "127.0.0.1", "*"],
        description="Allowed host patterns"
    )
    
    @field_validator('allowed_hosts', mode='before')
    @classmethod
    def parse_allowed_hosts(cls, v):
        """Parse allowed_hosts from string or list"""
        if isinstance(v, str):
            # Split by comma and strip whitespace
            return [host.strip() for host in v.split(',') if host.strip()]
        return v
    
    # Database settings
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/nexus.db",
        description="Database connection URL"
    )
    
    # AI/Ollama settings
    ai_provider: str = Field(default="ollama", description="AI provider (ollama, transformers)")
    ollama_base_url: str = Field(default="http://localhost:11434", description="Ollama API base URL")
    ai_model_name: str = Field(default="gpt-oss:20b", description="AI model to use")
    ai_timeout: int = Field(default=60, description="AI request timeout in seconds")
    max_reasoning_level: str = Field(
        default="medium", 
        description="Maximum AI reasoning level (low, medium, high)"
    )
    
    # SSH settings
    ssh_timeout: int = Field(default=30, description="SSH connection timeout")
    ssh_connection_timeout: int = Field(default=300, description="SSH idle connection timeout")
    max_ssh_connections: int = Field(default=1, description="Maximum concurrent SSH connections")
    ssh_key_path: Optional[str] = Field(default=None, description="Default SSH key path")
    ssh_default_safety_level: str = Field(default="cautious", description="Default command safety level")
    ssh_max_command_timeout: int = Field(default=120, description="Maximum command execution timeout")
    ssh_strict_host_key_checking: bool = Field(default=False, description="Enable SSH host key verification")
    
    # Logging settings
    log_level: str = Field(default="INFO", description="Logging level")
    log_to_file: bool = Field(default=True, description="Enable file logging")
    log_file_path: str = Field(default="./data/logs/nexus.log", description="Log file path")
    
    # File paths
    data_dir: Path = Field(default=Path("./data"), description="Data directory path")
    logs_dir: Path = Field(default=Path("./data/logs"), description="Logs directory path")
    
    # Feature flags
    serve_static: bool = Field(default=True, description="Serve static frontend files")
    enable_websockets: bool = Field(default=True, description="Enable WebSocket endpoints")
    enable_ai: bool = Field(default=True, description="Enable AI features")
    enable_audit_logging: bool = Field(default=True, description="Enable audit logging for SSH commands")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Ensure directories exist
        self.data_dir.mkdir(exist_ok=True)
        self.logs_dir.mkdir(exist_ok=True)


@lru_cache()
def get_settings() -> Settings:
    """Get application settings (cached)"""
    return Settings()