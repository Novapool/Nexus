"""
AI service for command generation and processing with gpt-oss integration
"""

import asyncio
import json
import logging
from typing import Dict, Any, List, Optional
import httpx
from backend.config.settings import get_settings
from backend.models.schemas import (
    AICommandResponse,
    AIExplainResponse,
    CommandValidationResult,
    ReasoningLevel,
    RiskLevel,
    OSType
)
from backend.core.exceptions import AIServiceError
from backend.core.safety_validator import SafetyValidator

logger = logging.getLogger(__name__)


class AIService:
    """Service for AI-powered command generation and processing with gpt-oss support"""
    
    def __init__(self):
        self.settings = get_settings()
        self.current_model = self.settings.ai_model_name
        self.client = httpx.AsyncClient(timeout=self.settings.ai_timeout)
        self.use_harmony_format = self.settings.ai_use_harmony_format and "gpt-oss" in self.current_model
    
    async def generate_command(
        self,
        prompt: str,
        server_context: Optional[Dict[str, Any]] = None,
        reasoning_level: ReasoningLevel = ReasoningLevel.MEDIUM,
        os_type: OSType = OSType.LINUX
    ) -> AICommandResponse:
        """Generate shell command from natural language prompt"""
        
        try:
            # Build context-aware prompt
            system_prompt = self._build_system_prompt(server_context, os_type, reasoning_level)
            full_prompt = self._build_command_prompt(prompt, server_context)
            
            # Call AI model with gpt-oss specific formatting
            response = await self._call_ollama(
                prompt=full_prompt,
                system_prompt=system_prompt,
                reasoning_level=reasoning_level
            )
            
            # Parse and validate response
            parsed_response = self._parse_command_response(response)
            
            # Validate command safety
            validation = await self.validate_command(
                parsed_response["command"],
                server_context
            )
            
            return AICommandResponse(
                command=parsed_response["command"],
                explanation=parsed_response["explanation"],
                is_safe=validation.is_safe,
                risk_level=validation.risk_level,
                warnings=validation.warnings,
                reasoning=parsed_response.get("reasoning"),
                alternatives=parsed_response.get("alternatives", [])
            )
            
        except Exception as e:
            logger.error(f"Command generation failed: {e}")
            raise AIServiceError(f"Failed to generate command: {str(e)}")
    
    async def explain_command(
        self,
        command: str,
        context: Optional[str] = None
    ) -> AIExplainResponse:
        """Explain what a shell command does"""
        
        try:
            system_prompt = """You are a helpful Linux system administrator assistant.
            Explain shell commands clearly and thoroughly. Break down complex commands 
            into their components and explain what each part does."""
            
            # Add gpt-oss reasoning prefix if using harmony format
            if self.use_harmony_format:
                system_prompt = f"Reasoning: {self.settings.ai_reasoning_level}\n\n{system_prompt}"
            
            prompt = f"""Please explain this shell command in detail:

Command: {command}

Please provide:
1. A clear explanation of what the command does
2. A breakdown of each component/option
3. Any potential warnings or considerations
4. Examples of similar usage if helpful

{f"Context: {context}" if context else ""}

Provide your response in JSON format:
{{
    "explanation": "clear explanation of what it does",
    "breakdown": [
        {{"component": "part of command", "explanation": "what this part does"}}
    ],
    "warnings": ["warning 1", "warning 2"],
    "examples": ["example 1", "example 2"]
}}"""
            
            response = await self._call_ollama(prompt, system_prompt)
            parsed_response = self._parse_explanation_response(response)
            
            return AIExplainResponse(
                command=command,
                explanation=parsed_response["explanation"],
                breakdown=parsed_response.get("breakdown", []),
                warnings=parsed_response.get("warnings", []),
                examples=parsed_response.get("examples", [])
            )
            
        except Exception as e:
            logger.error(f"Command explanation failed: {e}")
            raise AIServiceError(f"Failed to explain command: {str(e)}")
    
    async def validate_command(
        self,
        command: str,
        server_context: Optional[Dict[str, Any]] = None
    ) -> CommandValidationResult:
        """Validate if a command is safe to execute using centralized validator"""
        
        # Use centralized safety validator
        assessment = SafetyValidator.assess_command_risk(command, server_context)
        
        return CommandValidationResult(
            is_safe=assessment["is_safe"],
            risk_level=assessment["risk_level"],
            warnings=assessment["warnings"],
            explanation=assessment["explanation"],
            suggested_fixes=[]  # Could be enhanced with specific fix suggestions
        )
    
    async def list_models(self) -> List[str]:
        """List available AI models"""
        try:
            response = await self.client.get(f"{self.settings.ollama_base_url}/api/tags")
            if response.status_code == 200:
                data = response.json()
                return [model["name"] for model in data.get("models", [])]
            else:
                raise AIServiceError(f"Failed to list models: HTTP {response.status_code}")
        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            raise AIServiceError(f"Failed to list models: {str(e)}")
    
    async def switch_model(self, model_name: str) -> bool:
        """Switch to a different AI model"""
        try:
            # Check if model is available
            available_models = await self.list_models()
            if model_name not in available_models:
                return False
            
            self.current_model = model_name
            self.use_harmony_format = self.settings.ai_use_harmony_format and "gpt-oss" in model_name
            logger.info(f"Switched to model: {model_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to switch model: {e}")
            return False
    
    async def _call_ollama(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        reasoning_level: ReasoningLevel = ReasoningLevel.MEDIUM
    ) -> str:
        """Call Ollama API for text generation with gpt-oss support"""
        
        messages = []
        
        # Build system prompt for gpt-oss
        if system_prompt:
            # Add reasoning level for gpt-oss if using harmony format
            if self.use_harmony_format:
                if not system_prompt.startswith("Reasoning:"):
                    system_prompt = f"Reasoning: {reasoning_level.value}\n\n{system_prompt}"
            
            messages.append({"role": "system", "content": system_prompt})
        
        # Add user message
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": self.current_model,
            "messages": messages,
            "stream": False
        }
        
        # Add gpt-oss specific options if applicable
        if "gpt-oss" in self.current_model:
            payload.update({
                "options": {
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "max_tokens": 2048
                }
            })
        
        try:
            response = await self.client.post(
                f"{self.settings.ollama_base_url}/api/chat",
                json=payload
            )
            
            if response.status_code != 200:
                raise AIServiceError(f"Ollama API error: HTTP {response.status_code}")
            
            data = response.json()
            content = data["message"]["content"]
            
            # Log reasoning if using gpt-oss with chain of thought
            if self.use_harmony_format and self.settings.ai_enable_chain_of_thought:
                logger.debug(f"gpt-oss reasoning output: {content[:500]}...")
            
            return content
            
        except httpx.TimeoutException:
            raise AIServiceError("AI service timeout")
        except Exception as e:
            raise AIServiceError(f"AI service error: {str(e)}")
    
    def _build_system_prompt(
        self,
        server_context: Optional[Dict[str, Any]] = None,
        os_type: OSType = OSType.LINUX,
        reasoning_level: ReasoningLevel = ReasoningLevel.MEDIUM
    ) -> str:
        """Build system prompt with context"""
        
        base_prompt = """You are a Linux system administrator. Generate safe shell commands.

CRITICAL INSTRUCTIONS:
1. Respond with ONLY valid JSON
2. NO markdown code blocks (```json)
3. NO comments in JSON
4. Use this exact format:

{
    "command": "shell command here",
    "explanation": "what it does",
    "reasoning": "your thinking as one string",
    "alternatives": ["cmd1", "cmd2"]
}"""
        
        # Add gpt-oss reasoning prefix if using harmony format
        if self.use_harmony_format:
            base_prompt = f"Reasoning: {reasoning_level.value}\n\n{base_prompt}"
        
        # Add OS-specific context
        os_context = {
            OSType.UBUNTU: "Target OS: Ubuntu (use apt package manager)",
            OSType.DEBIAN: "Target OS: Debian (use apt package manager)", 
            OSType.CENTOS: "Target OS: CentOS (use yum package manager)",
            OSType.RHEL: "Target OS: RHEL (use yum package manager)",
            OSType.ALPINE: "Target OS: Alpine (use apk package manager)",
            OSType.MACOS: "Target OS: macOS (use brew package manager when needed)"
        }
        
        system_prompt = f"{base_prompt}\n\n{os_context.get(os_type, 'Target OS: Linux')}"
        
        # Add server context if available
        if server_context:
            context_info = f"""
Server Context:
- Hostname: {server_context.get('hostname', 'unknown')}
- OS: {server_context.get('os_type', 'linux')}
- Username: {server_context.get('username', 'user')}
- Package Manager: {server_context.get('system_info', {}).get('package_manager', 'unknown')}"""
            system_prompt += context_info
        
        return system_prompt
    
    def _build_command_prompt(
        self, 
        user_prompt: str, 
        server_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Build the full prompt for command generation"""
        
        prompt = f"""Generate a shell command for: {user_prompt}

CRITICAL: Respond with ONLY a JSON object. NO markdown code blocks, NO extra text.

Required format:
{{
    "command": "exact shell command",
    "explanation": "what it does",
    "reasoning": "your thinking process",
    "alternatives": ["alt1", "alt2"]
}}

Do NOT use ```json blocks. Return raw JSON only."""
        
        if server_context:
            prompt += f"\n\nServer: {server_context.get('os_type', 'linux')}"
        
        return prompt
    
    def _parse_command_response(self, response: str) -> Dict[str, Any]:
        """Parse AI response for command generation - Fixed version"""
        try:
            logger.debug(f"Parsing AI response: {response[:500]}...")
            
            # Handle gpt-oss chain of thought output with markdown
            if "```json" in response:
                # Extract JSON content from markdown blocks
                import re
                json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                    # Clean up comments and extra whitespace
                    json_str = re.sub(r'//.*', '', json_str)  # Remove // comments
                    json_str = re.sub(r'\s*//.*', '', json_str)  # Remove inline comments
                    parsed = json.loads(json_str)
                    
                    # Fix reasoning field if it's a list
                    if isinstance(parsed.get("reasoning"), list):
                        parsed["reasoning"] = "\n".join(str(item) for item in parsed["reasoning"])
                    
                    return parsed
            
            # Handle gpt-oss chain of thought output with thinking tags
            if self.use_harmony_format and "<thinking>" in response:
                import re
                json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                    parsed = json.loads(json_str)
                    # Ensure reasoning is a string
                    if isinstance(parsed.get("reasoning"), list):
                        parsed["reasoning"] = "\n".join(str(item) for item in parsed["reasoning"])
                    return parsed
            
            # Try to extract JSON from response without markdown
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            
            if start_idx != -1 and end_idx != 0:
                json_str = response[start_idx:end_idx]
                parsed = json.loads(json_str)
                
                # Fix reasoning field if it's a list
                if isinstance(parsed.get("reasoning"), list):
                    parsed["reasoning"] = "\n".join(str(item) for item in parsed["reasoning"])
                
                return parsed
                
        except Exception as e:
            logger.error(f"JSON parsing failed: {e}")
            
            # Enhanced fallback: extract command manually
            lines = [line.strip() for line in response.strip().split('\n') if line.strip()]
            command = "echo 'Could not parse command'"
            
            # Look for actual commands in the response
            for line in lines:
                if '"command":' in line:
                    # Extract command value
                    import re
                    match = re.search(r'"command":\s*"([^"]*)"', line)
                    if match:
                        command = match.group(1)
                        break
            
            return {
                "command": command,
                "explanation": "Command extracted from malformed AI response",
                "reasoning": "Fallback parsing used due to JSON parsing error",
                "alternatives": []
            }
    
    def _parse_explanation_response(self, response: str) -> Dict[str, Any]:
        """Parse AI response for command explanation"""
        try:
            # Handle gpt-oss chain of thought output
            if self.use_harmony_format and "<thinking>" in response:
                import re
                json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                    return json.loads(json_str)
            
            # Try JSON first
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            
            if start_idx != -1 and end_idx != 0:
                json_str = response[start_idx:end_idx]
                return json.loads(json_str)
        except json.JSONDecodeError:
            pass
        
        # Fallback: parse text response
        return {
            "explanation": response,
            "breakdown": [],
            "warnings": [],
            "examples": []
        }
    
    def _generate_safety_explanation(
        self, 
        command: str, 
        risk_level: RiskLevel, 
        warnings: List[str]
    ) -> str:
        """Generate explanation for command safety assessment"""
        
        explanations = {
            RiskLevel.SAFE: "This command appears to be safe to execute.",
            RiskLevel.LOW: "This command has minimal risk but should be used carefully.",
            RiskLevel.MEDIUM: "This command could modify system state. Review before executing.",
            RiskLevel.HIGH: "This command performs significant system changes. Use with caution.",
            RiskLevel.DANGEROUS: "This command is potentially destructive. DO NOT EXECUTE without expert review."
        }
        
        explanation = explanations[risk_level]
        
        if warnings:
            explanation += f" Warnings: {'; '.join(warnings)}"
        
        return explanation
    
    async def __aenter__(self):
        """Async context manager entry"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.client.aclose()
