"""
Simplified application configuration for Nexus
"""

from functools import lru_cache
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Simplified application settings with only essential configuration"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"  # Allow extra environment variables (like test settings)
    )
    
    # Core settings (8 essential settings)
    debug: bool = Field(default=False, description="Enable debug mode")
    host: str = Field(default="127.0.0.1", description="Host to bind the server")
    port: int = Field(default=8000, description="Port to bind the server")
    secret_key: str = Field(default="change-in-production", description="Secret key for security")
    database_url: str = Field(default="sqlite+aiosqlite:///./data/nexus.db", description="Database URL")
    
    # AI - gpt-oss specific settings (5 essential settings)
    ai_provider: str = Field(default="ollama", description="AI provider name")
    ollama_base_url: str = Field(default="http://localhost:11434", description="Ollama API base URL")
    ai_model_name: str = Field(default="gpt-oss:20b", description="AI model to use")
    ai_timeout: int = Field(default=120, description="AI request timeout in seconds")
    ai_reasoning_level: str = Field(default="medium", description="Default AI reasoning level")
    
    # SSH settings (3 essential settings)
    ssh_timeout: int = Field(default=30, description="SSH connection timeout")
    ssh_safety_level: str = Field(default="cautious", description="Default command safety level")
    ssh_max_connections: int = Field(default=10, description="Maximum concurrent SSH connections")
    
    # Features (5 essential settings)
    enable_operation_planning: bool = Field(default=False, description="Enable operation planning features")
    enable_quick_commands: bool = Field(default=True, description="Enable simple command execution")
    enable_ai: bool = Field(default=True, description="Enable AI features")
    serve_static: bool = Field(default=True, description="Serve static frontend files")
    
    # gpt-oss specific settings (2 additional settings)
    ai_use_harmony_format: bool = Field(default=True, description="Use gpt-oss harmony format")
    ai_enable_chain_of_thought: bool = Field(default=True, description="Enable chain-of-thought reasoning")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Ensure data directory exists
        data_dir = Path("./data")
        data_dir.mkdir(exist_ok=True)
        (data_dir / "logs").mkdir(exist_ok=True)


@lru_cache()
def get_settings() -> Settings:
    """Get application settings (cached)"""
    return Settings()

# Clear cache function for development
def clear_settings_cache():
    """Clear the settings cache"""
    get_settings.cache_clear()
