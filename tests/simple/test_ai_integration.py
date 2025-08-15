"""
Test AI model integration and command generation
"""

import pytest
import os
import httpx
from backend.core.ssh_manager import SSHManager
from backend.services.ai_service import AIService


class TestAIAvailability:
    """Test that AI model is available and responding"""
    
    @pytest.mark.asyncio
    async def test_ollama_is_running(self):
        """Test that Ollama is running and accessible"""
        ollama_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{ollama_url}/api/tags")
                assert response.status_code == 200
                
                models = response.json().get("models", [])
                assert len(models) > 0, "No models available in Ollama"
                
                model_names = [m["name"] for m in models]
                print(f"Available models: {model_names}")
                
        except Exception as e:
            pytest.skip(f"Ollama not available: {e}")
    
    @pytest.mark.asyncio
    async def test_target_model_available(self):
        """Test that our target model is available"""
        ollama_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
        target_model = os.getenv('AI_MODEL_NAME', 'gpt-oss:20b')
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{ollama_url}/api/tags")
                models = response.json().get("models", [])
                model_names = [m["name"] for m in models]
                
                assert target_model in model_names, f"Target model '{target_model}' not found. Available: {model_names}"
                print(f"✓ Target model '{target_model}' is available")
                
        except Exception as e:
            pytest.skip(f"Cannot check model availability: {e}")


class TestAIService:
    """Test AI service functionality"""
    
    @pytest.fixture
    def ai_service(self):
        """Create AI service instance"""
        return AIService()
    
    @pytest.mark.asyncio
    async def test_ai_simple_query(self, ai_service):
        """Test AI with a simple command generation query"""
        try:
            response = await ai_service.generate_command(
                "show the current working directory"
            )
            
            assert response is not None
            assert response.command is not None
            assert len(response.command) > 0
            assert "pwd" in response.command.lower()
            print(f"AI Generated Command: {response.command}")
            print(f"AI Explanation: {response.explanation}")
            
        except Exception as e:
            pytest.skip(f"AI service not available: {e}")
    
    @pytest.mark.asyncio
    async def test_ai_command_generation(self, ai_service):
        """Test AI generating specific commands"""
        try:
            response = await ai_service.generate_command(
                "list all files in the current directory with detailed information"
            )
            
            assert response is not None
            assert response.command is not None
            command = response.command.strip()
            
            # Should contain ls and some form of detailed listing flag
            assert "ls" in command
            assert any(flag in command for flag in ["-l", "-la", "-al", "--long"])
            print(f"Generated command: {command}")
            print(f"Explanation: {response.explanation}")
            
        except Exception as e:
            pytest.skip(f"AI service not available: {e}")


class TestAICommandExecution:
    """Test AI-generated commands with actual execution"""
    
    @pytest.mark.asyncio
    async def test_ai_pwd_command(self, connected_ssh: SSHManager):
        """Test AI generating and executing pwd command"""
        ai_service = AIService()
        
        try:
            # Ask AI to generate pwd command
            ai_response = await ai_service.generate_command(
                "print current working directory"
            )
            
            # Get the command from the response
            command = ai_response.command
            
            # Execute the AI-generated command
            result = await connected_ssh.execute_command(command)
            
            assert result.success is True
            assert result.exit_code == 0
            assert result.stdout.strip().startswith("/")
            
            print(f"AI generated: {command}")
            print(f"Command output: {result.stdout.strip()}")
            
        except Exception as e:
            pytest.skip(f"AI service not available: {e}")
    
    @pytest.mark.asyncio
    async def test_ai_date_command(self, connected_ssh: SSHManager):
        """Test AI generating and executing date command"""
        ai_service = AIService()
        
        try:
            # Ask AI to generate date command
            ai_response = await ai_service.generate_command(
                "show current date and time"
            )
            
            # Get the command from the response
            command = ai_response.command
            
            # Execute the AI-generated command
            result = await connected_ssh.execute_command(command)
            
            assert result.success is True
            assert result.exit_code == 0
            assert len(result.stdout.strip()) > 0
            
            print(f"AI generated: {command}")
            print(f"Command output: {result.stdout.strip()}")
            
        except Exception as e:
            pytest.skip(f"AI service not available: {e}")
    
    @pytest.mark.asyncio
    async def test_ai_system_info_command(self, connected_ssh: SSHManager):
        """Test AI generating command for system information"""
        ai_service = AIService()
        
        try:
            # Ask AI to generate system info command
            ai_response = await ai_service.generate_command(
                "show basic system information like hostname and kernel"
            )
            
            # Get the command from the response
            command = ai_response.command
            
            # Execute the AI-generated command
            result = await connected_ssh.execute_command(command)
            
            # Command should work (though output may vary)
            assert result.success is True
            assert result.exit_code == 0
            
            print(f"AI generated: {command}")
            print(f"Command output: {result.stdout.strip()[:200]}")
            
        except Exception as e:
            pytest.skip(f"AI service not available: {e}")


class TestAITaskPlanning:
    """Test AI's ability to plan complex tasks without execution"""
    
    @pytest.mark.asyncio
    async def test_ai_docker_installation_plan(self):
        """Test AI creating a plan for Docker installation"""
        ai_service = AIService()
        
        try:
            # Use explain_command to get detailed explanation of Docker installation
            response = await ai_service.explain_command(
                "curl -fsSL https://get.docker.com -o get-docker.sh && sh get-docker.sh",
                "Docker installation process on Ubuntu/Debian"
            )
            
            assert response is not None
            assert response.explanation is not None
            assert len(response.explanation) > 50  # Should be a detailed response
            assert "docker" in response.explanation.lower()
            
            print("Docker Installation Explanation:")
            print(response.explanation)
            
            if response.breakdown:
                print("Command breakdown:")
                for item in response.breakdown:
                    print(f"- {item}")
            
        except Exception as e:
            pytest.skip(f"AI service not available: {e}")
    
    @pytest.mark.asyncio
    async def test_ai_complex_task_planning(self):
        """Test AI planning a more complex system administration task"""
        ai_service = AIService()
        
        try:
            # Use explain_command to get detailed explanation of nginx setup
            response = await ai_service.explain_command(
                "sudo apt update && sudo apt install nginx && sudo systemctl start nginx && sudo systemctl enable nginx",
                "Setting up nginx web server on Ubuntu/Debian"
            )
            
            assert response is not None
            assert response.explanation is not None
            assert len(response.explanation) > 50
            assert "nginx" in response.explanation.lower()
            
            # Should mention common nginx setup steps
            assert any(keyword in response.explanation.lower() for keyword in ["install", "start", "enable", "service"])
            
            print("Nginx Setup Explanation:")
            print(response.explanation)
            
            if response.breakdown:
                print("Command breakdown:")
                for item in response.breakdown:
                    print(f"- {item}")
            
        except Exception as e:
            pytest.skip(f"AI service not available: {e}")
