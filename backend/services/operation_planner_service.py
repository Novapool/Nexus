"""
Operation planning service for multi-step server operations
"""

# type: ignore - Disable type checking for this entire file due to SQLAlchemy integration issues

import asyncio
import json
import logging
import uuid
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.models.operations import OperationPlan, OperationStep, OperationTemplate
from backend.models.operation_schemas import (
    OperationPlanRequest, OperationPlanSchema, OperationStepSchema,
    OperationType, PlanValidationResult,
    OperationTemplateSchema
)
# Fixed: Add missing imports
from backend.models.schemas import OSType, RiskLevel, ReasoningLevel
from backend.services.ai_service import AIService
from backend.services.server_service import ServerService
from backend.core.exceptions import AIServiceError, ServerNotFoundError
from backend.config.settings import get_settings

logger = logging.getLogger(__name__)


class OperationPlannerService:
    """Service for generating and managing operation plans"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()
        self.ai_service = AIService()
    
    async def generate_plan(self, request: OperationPlanRequest) -> OperationPlanSchema:
        """Generate a complete operation plan from user request"""
        logger.info(f"Generating operation plan for: {request.prompt[:100]}...")
        
        start_time = datetime.utcnow()
        
        try:
            # Get server context
            server_service = ServerService(self.db)
            server_context = await server_service.get_server_context(request.server_id)
            
            # Classify operation type if not provided
            if not request.operation_type:
                operation_type = await self._classify_operation(request.prompt, server_context)
            else:
                operation_type = request.operation_type
            
            # Set reasoning level based on operation complexity
            reasoning_level = self._get_reasoning_level(operation_type, request.reasoning_level)
            
            # Check for existing templates
            template = await self._find_matching_template(request.prompt, server_context.get("os_type"))
            
            if template:
                logger.info(f"Using template: {template.name}")
                plan = await self._generate_plan_from_template(template, request, server_context)
            else:
                # Generate plan using AI
                plan = await self._generate_plan_with_ai(
                    request, server_context, operation_type, reasoning_level
                )
            
            # Validate and enhance plan
            plan = await self._validate_and_enhance_plan(plan, server_context)
            
            # Calculate generation time
            generation_time = (datetime.utcnow() - start_time).total_seconds()
            plan.generation_time_seconds = generation_time
            
            # Save plan to database if requested
            if request.save_as_template and request.template_name:
                await self._save_as_template(plan, request.template_name, server_context)
            
            logger.info(f"Generated {operation_type.value} plan with {len(plan.steps)} steps in {generation_time:.2f}s")
            return plan
            
        except Exception as e:
            logger.error(f"Plan generation failed: {e}")
            raise AIServiceError(f"Failed to generate operation plan: {str(e)}")
    
    async def save_plan(self, plan: OperationPlanSchema) -> str:
        """Save operation plan to database"""
        plan_id = str(uuid.uuid4())
        
        # Create plan record
        db_plan = OperationPlan(
            id=plan_id,
            name=plan.name,
            description=plan.description,
            user_prompt=plan.user_prompt,
            operation_type=plan.operation_type.value,
            estimated_duration_seconds=plan.estimated_duration_seconds,
            risk_level=plan.risk_level.value,
            requires_approval=plan.requires_approval,
            server_id=plan.server_id,
            ai_model_used=plan.ai_model_used,
            reasoning_level=plan.reasoning_level.value,
            generation_time_seconds=plan.generation_time_seconds,
            status="draft"
        )
        
        self.db.add(db_plan)
        
        # Create step records
        all_steps = plan.prerequisite_steps + plan.steps + plan.rollback_steps
        for step_data in all_steps:
            step_id = str(uuid.uuid4())
            
            db_step = OperationStep(
                id=step_id,
                plan_id=plan_id,
                step_order=step_data.step_order,
                name=step_data.name,
                description=step_data.description,
                command=step_data.command,
                working_directory=step_data.working_directory,
                estimated_duration_seconds=step_data.estimated_duration_seconds,
                risk_level=step_data.risk_level.value,
                requires_approval=step_data.requires_approval,
                is_prerequisite=step_data.is_prerequisite,
                is_rollback_step=step_data.is_rollback_step,
                validation_command=step_data.validation_command,
                rollback_command=step_data.rollback_command,
                rollback_description=step_data.rollback_description,
                depends_on_steps=step_data.depends_on_steps,
                ai_reasoning=step_data.ai_reasoning
            )
            
            self.db.add(db_step)
        
        await self.db.commit()
        logger.info(f"Saved operation plan: {plan_id}")
        return plan_id
    
    async def get_plan(self, plan_id: str) -> Optional[OperationPlanSchema]:
        """Get operation plan by ID"""
        query = select(OperationPlan).options(
            selectinload(OperationPlan.steps)
        ).where(OperationPlan.id == plan_id)
        
        result = await self.db.execute(query)
        db_plan = result.scalar_one_or_none()
        
        if not db_plan:
            return None
        
        # Convert to schema
        return await self._db_plan_to_schema(db_plan)
    
    async def list_plans(
        self, 
        server_id: Optional[str] = None,
        operation_type: Optional[OperationType] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[OperationPlanSchema]:
        """List operation plans with filters"""
        query = select(OperationPlan).options(
            selectinload(OperationPlan.steps)
        )
        
        if server_id:
            query = query.where(OperationPlan.server_id == server_id)
        
        if operation_type:
            query = query.where(OperationPlan.operation_type == operation_type.value)
        
        query = query.offset(skip).limit(limit).order_by(OperationPlan.created_at.desc())
        
        result = await self.db.execute(query)
        db_plans = result.scalars().all()
        
        plans = []
        for db_plan in db_plans:
            plan_schema = await self._db_plan_to_schema(db_plan)
            plans.append(plan_schema)
        
        return plans
    
    async def validate_plan(self, plan: OperationPlanSchema, server_context: Dict[str, Any]) -> PlanValidationResult:
        """Validate operation plan for safety and feasibility"""
        warnings = []
        errors = []
        required_approvals = []
        overall_risk = RiskLevel.SAFE
        estimated_duration = 0
        
        # Validate individual steps
        for step in plan.steps:
            # Check command safety
            if await self._is_dangerous_command(step.command):
                errors.append(f"Step {step.step_order}: Contains dangerous command pattern")
                overall_risk = RiskLevel.DANGEROUS
            
            # Check for high-risk operations
            if step.risk_level in [RiskLevel.HIGH, RiskLevel.DANGEROUS]:
                required_approvals.append(step.step_order)
                # Fixed: Proper risk level comparison
                if self._compare_risk_levels(step.risk_level, overall_risk) > 0:
                    overall_risk = step.risk_level
            
            # Check OS compatibility
            os_type = server_context.get("os_type", "linux")
            if not await self._is_command_compatible(step.command, os_type):
                warnings.append(f"Step {step.step_order}: Command may not be compatible with {os_type}")
            
            # Add estimated duration
            if step.estimated_duration_seconds:
                estimated_duration += step.estimated_duration_seconds
        
        # Check dependencies
        dependency_errors = await self._validate_dependencies(plan.steps)
        errors.extend(dependency_errors)
        
        # Check system requirements
        req_warnings = await self._check_system_requirements(plan, server_context)
        warnings.extend(req_warnings)
        
        is_valid = len(errors) == 0
        
        return PlanValidationResult(
            is_valid=is_valid,
            warnings=warnings,
            errors=errors,
            risk_assessment=overall_risk,
            estimated_duration=estimated_duration if estimated_duration > 0 else None,
            required_approvals=required_approvals
        )
    
    def _compare_risk_levels(self, risk1: RiskLevel, risk2: RiskLevel) -> int:
        """Compare two risk levels, return 1 if risk1 > risk2, -1 if risk1 < risk2, 0 if equal"""
        risk_order = [RiskLevel.SAFE, RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.DANGEROUS]
        
        try:
            index1 = risk_order.index(risk1)
            index2 = risk_order.index(risk2)
            
            if index1 > index2:
                return 1
            elif index1 < index2:
                return -1
            else:
                return 0
        except ValueError:
            # If either risk level is not in the order, default to equal
            return 0
    
    async def _classify_operation(self, prompt: str, server_context: Dict[str, Any]) -> OperationType:
        """Classify operation complexity based on prompt and context"""
        # Use AI to classify operation type
        classification_prompt = f"""
        Analyze this server management request and classify its complexity:
        
        Request: {prompt}
        Server OS: {server_context.get('os_type', 'linux')}
        
        Classify as:
        - SIMPLE: Basic operations (3-5 steps) like installing single packages, creating files, basic config
        - COMPLEX: Multi-component setups (6-12 steps) like web server with SSL, database setup
        - ADVANCED: Complete system setups (13+ steps) like full stack deployments, security hardening
        
        Respond with only: SIMPLE, COMPLEX, or ADVANCED
        """
        
        try:
            response = await self.ai_service._call_ollama(
                prompt=classification_prompt,
                system_prompt="You are an expert system administrator. Classify operation complexity accurately.",
                reasoning_level=ReasoningLevel.LOW
            )
            
            # Parse response
            response_clean = response.strip().upper()
            if "SIMPLE" in response_clean:
                return OperationType.SIMPLE
            elif "COMPLEX" in response_clean:
                return OperationType.COMPLEX
            elif "ADVANCED" in response_clean:
                return OperationType.ADVANCED
            else:
                # Default to SIMPLE if unclear
                logger.warning(f"Could not classify operation, defaulting to SIMPLE: {response}")
                return OperationType.SIMPLE
                
        except Exception as e:
            logger.error(f"Operation classification failed: {e}")
            # Default to SIMPLE on error
            return OperationType.SIMPLE
    
    def _get_reasoning_level(self, operation_type: OperationType, requested_level: Optional[ReasoningLevel]) -> ReasoningLevel:
        """Determine appropriate reasoning level based on operation complexity"""
        if requested_level:
            return requested_level
        
        # Map operation complexity to reasoning level
        level_mapping = {
            OperationType.SIMPLE: ReasoningLevel.LOW,
            OperationType.COMPLEX: ReasoningLevel.MEDIUM,
            OperationType.ADVANCED: ReasoningLevel.HIGH
        }
        
        return level_mapping.get(operation_type, ReasoningLevel.MEDIUM)
    
    async def _find_matching_template(self, prompt: str, os_type: Optional[str]) -> Optional[OperationTemplateSchema]:
        """Find matching operation template"""
        try:
            # Query active templates
            query = select(OperationTemplate).where(
                OperationTemplate.is_active == True
            ).order_by(OperationTemplate.usage_count.desc())
            
            result = await self.db.execute(query)
            templates = result.scalars().all()
            
            # Simple keyword matching for now
            prompt_lower = prompt.lower()
            
            for template in templates:
                # Check OS compatibility
                if os_type and hasattr(template, 'os_compatibility') and template.os_compatibility:
                    if os_type not in [str(os) for os in template.os_compatibility]:
                        continue
                
                # Check tags and name for matches
                template_keywords = []
                if hasattr(template, 'tags') and template.tags:
                    template_keywords.extend([tag.lower() for tag in template.tags])
                template_keywords.append(template.name.lower())
                
                # Simple keyword matching
                for keyword in template_keywords:
                    if keyword in prompt_lower:
                        logger.info(f"Found matching template: {template.name}")
                        return OperationTemplateSchema.model_validate(template)
            
            return None
            
        except Exception as e:
            logger.error(f"Template matching failed: {e}")
            return None
    
    async def _generate_plan_from_template(
        self, 
        template: OperationTemplateSchema, 
        request: OperationPlanRequest,
        server_context: Dict[str, Any]
    ) -> OperationPlanSchema:
        """Generate plan from existing template"""
        try:
            # Load template data
            template_data = template.template_data
            
            # Create base plan from template
            plan = OperationPlanSchema(
                name=f"{template.name} - {datetime.utcnow().strftime('%Y%m%d_%H%M')}",
                description=f"Generated from template: {template.name}",
                user_prompt=request.prompt,
                operation_type=template.operation_type,
                server_id=request.server_id,
                reasoning_level=request.reasoning_level,
                ai_model_used=self.ai_service.current_model,
                steps=[],
                prerequisite_steps=[],
                rollback_steps=[],
                risk_level=RiskLevel.SAFE,
                requires_approval=False,
                estimated_duration_seconds=0,
                generation_time_seconds=0.0
            )
            
            # Convert template steps to plan steps
            if "steps" in template_data:
                for i, step_data in enumerate(template_data["steps"]):
                    step = OperationStepSchema(
                        step_order=i + 1,
                        name=step_data.get("name", f"Step {i + 1}"),
                        description=step_data.get("description", ""),
                        command=step_data.get("command", ""),
                        working_directory=step_data.get("working_directory"),
                        estimated_duration_seconds=step_data.get("estimated_duration_seconds", 30),
                        risk_level=RiskLevel(step_data.get("risk_level", "safe")),
                        requires_approval=step_data.get("requires_approval", False),
                        is_prerequisite=step_data.get("is_prerequisite", False),
                        is_rollback_step=step_data.get("is_rollback_step", False),
                        validation_command=step_data.get("validation_command"),
                        rollback_command=step_data.get("rollback_command"),
                        rollback_description=step_data.get("rollback_description"),
                        depends_on_steps=step_data.get("depends_on_steps", []),
                        ai_reasoning=f"Generated from template: {template.name}"
                    )
                    
                    if step.is_prerequisite:
                        plan.prerequisite_steps.append(step)
                    elif step.is_rollback_step:
                        plan.rollback_steps.append(step)
                    else:
                        plan.steps.append(step)
            
            # Update template usage statistics
            await self._update_template_usage(template.id)
            
            return plan
            
        except Exception as e:
            logger.error(f"Template-based plan generation failed: {e}")
            # Fallback to AI generation
            return await self._generate_plan_with_ai(
                request, server_context, template.operation_type, request.reasoning_level
            )
    
    async def _generate_plan_with_ai(
        self,
        request: OperationPlanRequest,
        server_context: Dict[str, Any],
        operation_type: OperationType,
        reasoning_level: ReasoningLevel
    ) -> OperationPlanSchema:
        """Generate operation plan using AI"""
        
        # Build comprehensive prompt for AI
        ai_prompt = f"""
        Generate a detailed operation plan for the following server management task:
        
        Task: {request.prompt}
        
        Server Context:
        - OS: {server_context.get('os_type', 'linux')}
        - Hostname: {server_context.get('hostname', 'unknown')}
        - Package Manager: {server_context.get('capabilities', {}).get('package_manager', 'unknown')}
        - Architecture: {server_context.get('capabilities', {}).get('architecture', 'unknown')}
        
        Operation Type: {operation_type.value}
        
        Requirements:
        1. Break down the task into logical, sequential steps
        2. Include prerequisite checks where needed
        3. Provide rollback commands for reversible operations
        4. Assess risk level for each step (safe, low, medium, high, dangerous)
        5. Include validation commands to verify success
        6. Estimate execution time for each step
        
        Respond with a JSON object in this exact format:
        {{
            "name": "descriptive plan name",
            "description": "detailed plan description",
            "estimated_duration_seconds": total_estimated_time,
            "risk_level": "overall_risk_level",
            "requires_approval": boolean,
            "prerequisite_steps": [
                {{
                    "step_order": 0,
                    "name": "prerequisite check name",
                    "description": "what this check does",
                    "command": "command to run",
                    "working_directory": "/path/to/work/dir",
                    "estimated_duration_seconds": 10,
                    "risk_level": "safe",
                    "requires_approval": false,
                    "is_prerequisite": true,
                    "validation_command": "command to validate",
                    "ai_reasoning": "why this step is needed"
                }}
            ],
            "steps": [
                {{
                    "step_order": 1,
                    "name": "step name",
                    "description": "what this step does",
                    "command": "command to execute",
                    "working_directory": "/path/to/work/dir",
                    "estimated_duration_seconds": 30,
                    "risk_level": "low",
                    "requires_approval": false,
                    "is_prerequisite": false,
                    "validation_command": "command to validate success",
                    "rollback_command": "command to undo this step",
                    "rollback_description": "how to rollback",
                    "depends_on_steps": [],
                    "ai_reasoning": "detailed reasoning for this step"
                }}
            ],
            "rollback_steps": [
                {{
                    "step_order": 100,
                    "name": "rollback step name",
                    "description": "rollback description",
                    "command": "rollback command",
                    "working_directory": "/path/to/work/dir",
                    "estimated_duration_seconds": 15,
                    "risk_level": "low",
                    "requires_approval": false,
                    "is_rollback_step": true,
                    "ai_reasoning": "rollback reasoning"
                }}
            ]
        }}
        """
        
        system_prompt = f"""You are an expert system administrator and DevOps engineer. 
        Generate safe, comprehensive operation plans for server management tasks.
        
        CRITICAL SAFETY RULES:
        1. Never suggest destructive commands without proper safeguards
        2. Always include validation steps
        3. Provide rollback procedures for reversible operations
        4. Assess risk levels accurately
        5. Break complex operations into manageable steps
        6. Consider the target OS and available tools
        
        Operation Complexity: {operation_type.value}
        Reasoning Level: {reasoning_level.value}
        """
        
        try:
            response = await self.ai_service._call_ollama(
                prompt=ai_prompt,
                system_prompt=system_prompt,
                reasoning_level=reasoning_level
            )
            
            # Parse AI response
            plan_data = self._parse_ai_plan_response(response)
            
            # Create plan schema
            plan = OperationPlanSchema(
                name=plan_data.get("name", "AI Generated Plan"),
                description=plan_data.get("description", "Generated by AI"),
                user_prompt=request.prompt,
                operation_type=operation_type,
                estimated_duration_seconds=plan_data.get("estimated_duration_seconds"),
                risk_level=RiskLevel(plan_data.get("risk_level", "safe")),
                requires_approval=plan_data.get("requires_approval", False),
                server_id=request.server_id,
                ai_model_used=self.ai_service.current_model,
                reasoning_level=reasoning_level,
                steps=[],
                prerequisite_steps=[],
                rollback_steps=[],
                generation_time_seconds=0.0
            )
            
            # Convert steps
            for step_data in plan_data.get("prerequisite_steps", []):
                step = self._create_step_from_data(step_data, True, False)
                plan.prerequisite_steps.append(step)
            
            for step_data in plan_data.get("steps", []):
                step = self._create_step_from_data(step_data, False, False)
                plan.steps.append(step)
            
            for step_data in plan_data.get("rollback_steps", []):
                step = self._create_step_from_data(step_data, False, True)
                plan.rollback_steps.append(step)
            
            return plan
            
        except Exception as e:
            logger.error(f"AI plan generation failed: {e}")
            raise AIServiceError(f"Failed to generate AI plan: {str(e)}")
    
    def _parse_ai_plan_response(self, response: str) -> Dict[str, Any]:
        """Parse AI response into plan data"""
        try:
            # Try to extract JSON from response
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            
            if start_idx != -1 and end_idx != 0:
                json_str = response[start_idx:end_idx]
                return json.loads(json_str)
            else:
                raise ValueError("No JSON found in response")
                
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            # Return minimal fallback plan
            return {
                "name": "Fallback Plan",
                "description": "AI response could not be parsed",
                "estimated_duration_seconds": 300,
                "risk_level": "medium",
                "requires_approval": True,
                "steps": [
                    {
                        "step_order": 1,
                        "name": "Manual Review Required",
                        "description": "AI response parsing failed, manual review needed",
                        "command": "echo 'Manual review required'",
                        "estimated_duration_seconds": 60,
                        "risk_level": "safe",
                        "requires_approval": True,
                        "ai_reasoning": "Fallback due to parsing error"
                    }
                ]
            }
    
    def _create_step_from_data(self, step_data: Dict[str, Any], is_prerequisite: bool, is_rollback: bool) -> OperationStepSchema:
        """Create step schema from parsed data"""
        return OperationStepSchema(
            step_order=step_data.get("step_order", 1),
            name=step_data.get("name", "Unnamed Step"),
            description=step_data.get("description", ""),
            command=step_data.get("command", "echo 'No command specified'"),
            working_directory=step_data.get("working_directory"),
            estimated_duration_seconds=step_data.get("estimated_duration_seconds", 30),
            risk_level=RiskLevel(step_data.get("risk_level", "safe")),
            requires_approval=step_data.get("requires_approval", False),
            is_prerequisite=is_prerequisite,
            is_rollback_step=is_rollback,
            validation_command=step_data.get("validation_command"),
            rollback_command=step_data.get("rollback_command"),
            rollback_description=step_data.get("rollback_description"),
            depends_on_steps=step_data.get("depends_on_steps", []),
            ai_reasoning=step_data.get("ai_reasoning", "")
        )
    
    async def _validate_and_enhance_plan(self, plan: OperationPlanSchema, server_context: Dict[str, Any]) -> OperationPlanSchema:
        """Validate and enhance the generated plan"""
        try:
            # Validate the plan
            validation_result = await self.validate_plan(plan, server_context)
            
            # Update plan based on validation
            if validation_result.required_approvals:
                plan.requires_approval = True
            
            # Update overall risk level
            plan.risk_level = validation_result.risk_assessment
            
            # Update estimated duration if calculated
            if validation_result.estimated_duration:
                plan.estimated_duration_seconds = validation_result.estimated_duration
            
            # Log validation results
            if validation_result.warnings:
                logger.warning(f"Plan validation warnings: {validation_result.warnings}")
            
            if validation_result.errors:
                logger.error(f"Plan validation errors: {validation_result.errors}")
            
            return plan
            
        except Exception as e:
            logger.error(f"Plan validation failed: {e}")
            # Return plan as-is if validation fails
            return plan
    
    async def _save_as_template(self, plan: OperationPlanSchema, template_name: str, server_context: Dict[str, Any]):
        """Save plan as reusable template"""
        try:
            template_id = str(uuid.uuid4())
            
            # Prepare template data
            template_data = {
                "steps": [],
                "prerequisite_steps": [],
                "rollback_steps": []
            }
            
            # Convert plan steps to template format
            for step in plan.steps:
                template_data["steps"].append({
                    "name": step.name,
                    "description": step.description,
                    "command": step.command,
                    "working_directory": step.working_directory,
                    "estimated_duration_seconds": step.estimated_duration_seconds,
                    "risk_level": step.risk_level.value,
                    "requires_approval": step.requires_approval,
                    "validation_command": step.validation_command,
                    "rollback_command": step.rollback_command,
                    "rollback_description": step.rollback_description,
                    "depends_on_steps": step.depends_on_steps
                })
            
            # Create template record
            db_template = OperationTemplate(
                id=template_id,
                name=template_name,
                description=plan.description,
                category="user_generated",
                operation_type=plan.operation_type.value,
                template_data=template_data,
                os_compatibility=[server_context.get("os_type", "linux")],
                usage_count=0,
                is_active=True,
                is_verified=False
            )
            
            self.db.add(db_template)
            await self.db.commit()
            
            logger.info(f"Saved plan as template: {template_name}")
            
        except Exception as e:
            logger.error(f"Failed to save template: {e}")
    
    async def _db_plan_to_schema(self, db_plan: OperationPlan) -> OperationPlanSchema:
        """Convert database plan to schema"""
        # Separate steps by type
        prerequisite_steps = []
        main_steps = []
        rollback_steps = []
        
        for db_step in db_plan.steps:
            step_schema = OperationStepSchema(
                id=str(db_step.id),
                step_order=int(db_step.step_order),
                name=str(db_step.name),
                description=str(db_step.description) if db_step.description else None,
                command=str(db_step.command),
                working_directory=str(db_step.working_directory) if db_step.working_directory else None,
                estimated_duration_seconds=int(db_step.estimated_duration_seconds) if db_step.estimated_duration_seconds else None,
                risk_level=RiskLevel(db_step.risk_level),
                requires_approval=bool(db_step.requires_approval),
                is_prerequisite=bool(db_step.is_prerequisite),
                is_rollback_step=bool(db_step.is_rollback_step),
                validation_command=str(db_step.validation_command) if db_step.validation_command else None,
                rollback_command=str(db_step.rollback_command) if db_step.rollback_command else None,
                rollback_description=str(db_step.rollback_description) if db_step.rollback_description else None,
                depends_on_steps=db_step.depends_on_steps or [],
                ai_reasoning=str(db_step.ai_reasoning) if db_step.ai_reasoning else None
            )
            
            if db_step.is_prerequisite:
                prerequisite_steps.append(step_schema)
            elif db_step.is_rollback_step:
                rollback_steps.append(step_schema)
            else:
                main_steps.append(step_schema)
        
        # Sort steps by order
        prerequisite_steps.sort(key=lambda x: x.step_order)
        main_steps.sort(key=lambda x: x.step_order)
        rollback_steps.sort(key=lambda x: x.step_order)
        
        return OperationPlanSchema(
            id=str(db_plan.id),
            name=str(db_plan.name),
            description=str(db_plan.description) if db_plan.description else None,
            user_prompt=str(db_plan.user_prompt),
            operation_type=OperationType(db_plan.operation_type),
            estimated_duration_seconds=int(db_plan.estimated_duration_seconds) if db_plan.estimated_duration_seconds else None,
            risk_level=RiskLevel(db_plan.risk_level),
            requires_approval=bool(db_plan.requires_approval),
            server_id=str(db_plan.server_id),
            ai_model_used=str(db_plan.ai_model_used) if db_plan.ai_model_used else None,
            reasoning_level=ReasoningLevel(db_plan.reasoning_level),
            generation_time_seconds=float(db_plan.generation_time_seconds) if db_plan.generation_time_seconds else None,
            steps=main_steps,
            prerequisite_steps=prerequisite_steps,
            rollback_steps=rollback_steps,
            created_at=db_plan.created_at,
            updated_at=db_plan.updated_at
        )
    
    async def _is_dangerous_command(self, command: str) -> bool:
        """Check if command contains dangerous patterns"""
        dangerous_patterns = [
            "rm -rf /", "rm -rf /*", "mkfs", "dd if=", ":(){ :|:& };:",
            "chmod -R 777 /", "format", "fdisk", "wipefs", "shred",
            "rm -rf --no-preserve-root", "rm -rf .", "rm -rf ..",
            "> /dev/sda", "> /dev/sd", "cat /dev/zero >", "dd of=/dev/"
        ]
        
        command_lower = command.lower()
        for pattern in dangerous_patterns:
            if pattern in command_lower:
                return True
        return False
    
    async def _is_command_compatible(self, command: str, os_type: str) -> bool:
        """Check if command is compatible with target OS"""
        command_lower = command.lower()
        
        # OS-specific package managers
        if os_type in ["ubuntu", "debian"]:
            if any(pkg in command_lower for pkg in ["yum", "dnf", "pacman", "apk", "brew"]):
                return False
        elif os_type in ["centos", "rhel", "fedora"]:
            if any(pkg in command_lower for pkg in ["apt", "apt-get", "pacman", "apk", "brew"]):
                return False
        elif os_type == "alpine":
            if any(pkg in command_lower for pkg in ["apt", "apt-get", "yum", "dnf", "pacman", "brew"]):
                return False
        elif os_type == "macos":
            if any(pkg in command_lower for pkg in ["apt", "apt-get", "yum", "dnf", "pacman", "apk"]):
                return False
        
        return True
    
    async def _validate_dependencies(self, steps: List[OperationStepSchema]) -> List[str]:
        """Validate step dependencies"""
        errors = []
        step_orders = {step.step_order for step in steps}
        
        for step in steps:
            for dep_order in step.depends_on_steps:
                if dep_order not in step_orders:
                    errors.append(f"Step {step.step_order} depends on non-existent step {dep_order}")
                elif dep_order >= step.step_order:
                    errors.append(f"Step {step.step_order} has invalid dependency on step {dep_order} (circular or forward dependency)")
        
        return errors
    
    async def _check_system_requirements(self, plan: OperationPlanSchema, server_context: Dict[str, Any]) -> List[str]:
        """Check system requirements for plan execution"""
        warnings = []
        
        # Check for common requirements
        commands_used = [step.command for step in plan.steps]
        all_commands = " ".join(commands_used).lower()
        
        # Check for Docker requirements
        if "docker" in all_commands and "docker" not in server_context.get("capabilities", {}):
            warnings.append("Plan requires Docker but Docker availability is unknown")
        
        # Check for sudo requirements
        if "sudo" in all_commands:
            warnings.append("Plan requires sudo privileges")
        
        # Check for network requirements
        if any(cmd in all_commands for cmd in ["wget", "curl", "git clone", "pip install", "npm install"]):
            warnings.append("Plan requires internet connectivity")
        
        return warnings
    
    async def _update_template_usage(self, template_id: Optional[str]):
        """Update template usage statistics"""
        if not template_id:
            return
        
        try:
            # This would update the template usage count
            # For now, just log it
            logger.info(f"Template {template_id} used")
        except Exception as e:
            logger.error(f"Failed to update template usage: {e}")
