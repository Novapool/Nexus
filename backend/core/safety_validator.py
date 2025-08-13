"""
Centralized safety validation for command execution
"""

import logging
from typing import List, Dict, Any, Optional
from backend.models.schemas import SafetyLevel, RiskLevel, OSType

logger = logging.getLogger(__name__)


class SafetyValidator:
    """Centralized command safety validation"""
    
    # Define risk patterns
    DANGEROUS_PATTERNS = [
        "rm -rf /", "rm -rf /*", "mkfs", "dd if=", ":(){ :|:& };:",
        "chmod -R 777 /", "chown -R", "sudo rm", "format", "fdisk",
        "shutdown -h now", "halt", "poweroff"
    ]
    
    HIGH_RISK_PATTERNS = [
        "sudo", "rm -rf", "chmod 777", "wget | sh", "curl | sh",
        "mv /etc", "cp /etc", "shutdown", "reboot", "init 0",
        "systemctl stop", "service stop", "kill -9"
    ]
    
    MEDIUM_RISK_PATTERNS = [
        "rm ", "rmdir", "chmod", "chown", "mv", "cp /", "crontab",
        "iptables", "ufw", "firewall", "passwd", "usermod"
    ]
    
    # Safety level hierarchy (lower number = safer)
    RISK_HIERARCHY = {
        RiskLevel.SAFE: 0,
        RiskLevel.LOW: 1,
        RiskLevel.MEDIUM: 2,
        RiskLevel.HIGH: 3,
        RiskLevel.DANGEROUS: 4
    }
    
    SAFETY_LIMITS = {
        SafetyLevel.PARANOID: 0,    # Allow safe only
        SafetyLevel.SAFE: 1,        # Allow low risk only
        SafetyLevel.CAUTIOUS: 2,    # Allow medium risk
        SafetyLevel.NORMAL: 3,      # Allow high risk
        SafetyLevel.PERMISSIVE: 4   # Allow dangerous
    }
    
    @classmethod
    def assess_command_risk(
        cls, 
        command: str, 
        server_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Assess the risk level of a command"""
        
        warnings = []
        risk_level = RiskLevel.SAFE
        is_safe = True
        
        command_lower = command.lower().strip()
        
        # Check for dangerous patterns first
        for pattern in cls.DANGEROUS_PATTERNS:
            if pattern in command_lower:
                risk_level = RiskLevel.DANGEROUS
                is_safe = False
                warnings.append(f"Contains dangerous pattern: {pattern}")
                break  # Stop at first dangerous pattern
        
        # If not dangerous, check for high risk patterns
        if is_safe:
            for pattern in cls.HIGH_RISK_PATTERNS:
                if pattern in command_lower:
                    risk_level = RiskLevel.HIGH
                    warnings.append(f"High-risk operation: {pattern}")
                    break  # Stop at first high-risk pattern
            
            # If not high risk, check for medium risk patterns
            if risk_level == RiskLevel.SAFE:
                for pattern in cls.MEDIUM_RISK_PATTERNS:
                    if pattern in command_lower:
                        risk_level = RiskLevel.MEDIUM
                        warnings.append(f"Potentially risky operation: {pattern}")
                        break  # Stop at first medium-risk pattern
        
        # Additional context-based validation
        if server_context:
            context_warnings = cls._validate_context(command_lower, server_context)
            warnings.extend(context_warnings)
        
        # Generate explanation
        explanation = cls._generate_risk_explanation(command, risk_level, warnings)
        
        return {
            "is_safe": is_safe,
            "risk_level": risk_level,
            "warnings": warnings,
            "explanation": explanation
        }
    
    @classmethod
    def is_safety_acceptable(
        cls, 
        risk_level: RiskLevel, 
        safety_level: SafetyLevel
    ) -> bool:
        """Check if command risk level is acceptable for given safety level"""
        
        command_risk = cls.RISK_HIERARCHY.get(risk_level, 4)
        max_allowed_risk = cls.SAFETY_LIMITS.get(safety_level, 0)
        
        return command_risk <= max_allowed_risk
    
    @classmethod
    def get_safety_recommendation(
        cls, 
        risk_level: RiskLevel, 
        current_safety: SafetyLevel
    ) -> Optional[SafetyLevel]:
        """Get recommended safety level for a given risk level"""
        
        for safety_level, max_risk in cls.SAFETY_LIMITS.items():
            if cls.RISK_HIERARCHY.get(risk_level, 4) <= max_risk:
                return safety_level
        
        return SafetyLevel.PERMISSIVE
    
    @classmethod
    def _validate_context(
        cls, 
        command_lower: str, 
        server_context: Dict[str, Any]
    ) -> List[str]:
        """Validate command against server context"""
        
        warnings = []
        os_type = server_context.get("os_type", OSType.LINUX)
        
        # OS-specific package manager warnings
        if os_type == OSType.MACOS:
            if any(pm in command_lower for pm in ["apt", "yum", "dnf"]):
                warnings.append("Using Linux package manager on macOS - should use brew instead")
        elif os_type in [OSType.UBUNTU, OSType.DEBIAN]:
            if any(pm in command_lower for pm in ["yum", "dnf", "brew"]):
                warnings.append("Using non-Debian package manager on Debian-based system")
        elif os_type in [OSType.CENTOS, OSType.RHEL]:
            if any(pm in command_lower for pm in ["apt", "brew"]):
                warnings.append("Using non-RedHat package manager on RedHat-based system")
        
        # Check for potentially destructive operations on important directories
        if server_context.get("username") == "root":
            if any(op in command_lower for op in ["rm", "mv", "chmod"]):
                warnings.append("Potentially destructive operation as root user")
        
        return warnings
    
    @classmethod
    def _generate_risk_explanation(
        cls, 
        command: str, 
        risk_level: RiskLevel, 
        warnings: List[str]
    ) -> str:
        """Generate explanation for command risk assessment"""
        
        explanations = {
            RiskLevel.SAFE: "This command appears to be safe to execute.",
            RiskLevel.LOW: "This command has minimal risk but should be used carefully.",
            RiskLevel.MEDIUM: "This command could modify system state. Review before executing.",
            RiskLevel.HIGH: "This command performs significant system changes. Use with caution.",
            RiskLevel.DANGEROUS: "This command is potentially destructive. DO NOT EXECUTE without expert review."
        }
        
        explanation = explanations.get(risk_level, "Unknown risk level.")
        
        if warnings:
            explanation += f" Warnings: {'; '.join(warnings)}"
        
        return explanation
    
    @classmethod
    def get_safety_tips(cls, risk_level: RiskLevel) -> List[str]:
        """Get safety tips for a given risk level"""
        
        tips = {
            RiskLevel.SAFE: [
                "Command appears safe to execute",
                "Consider testing in a non-production environment first"
            ],
            RiskLevel.LOW: [
                "Review command output carefully",
                "Ensure you have proper backups",
                "Test in a safe environment first"
            ],
            RiskLevel.MEDIUM: [
                "Create system backup before execution",
                "Review command parameters carefully",
                "Consider running with --dry-run flag if available",
                "Have rollback plan ready"
            ],
            RiskLevel.HIGH: [
                "STOP: Review this command with a system administrator",
                "Create full system backup",
                "Test in isolated environment first",
                "Prepare detailed rollback procedure",
                "Consider alternative safer approaches"
            ],
            RiskLevel.DANGEROUS: [
                "DO NOT EXECUTE without expert review",
                "This command can cause irreversible damage",
                "Seek alternative solutions",
                "If absolutely necessary, test on disposable system first",
                "Have complete disaster recovery plan ready"
            ]
        }
        
        return tips.get(risk_level, ["Unknown risk level - proceed with extreme caution"])
