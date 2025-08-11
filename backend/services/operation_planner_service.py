"""
Operation planning service for multi-step server operations
"""

# type: ignore - Disable type checking for this entire file due to SQLAlchemy integration issues

import asyncio
import json
import logging
import uuid
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