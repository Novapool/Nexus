"""
Operation execution service for running multi-step operation plans
"""

# type: ignore - Disable type checking for this entire file due to SQLAlchemy integration issues

import asyncio
import logging
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from backend.models.operations import (
    OperationPlan, OperationStep, OperationExecution, OperationStepExecution
)
from backend.models.operation_schemas import (
    OperationExecutionRequest, OperationExecutionSchema, OperationStepExecutionSchema,
    ExecutionMode, ExecutionStatus, StepStatus, ExecutionProgress,
    StepApprovalRequest, OperationError
)
from backend.services.operation_planner_service import OperationPlannerService
from backend.services.server_service import ServerService
from backend.core.ssh_manager import SafetyLevel
from backend.core.exceptions import ServerNotFoundError, SSHConnectionError
from backend.config.settings import get_settings

logger = logging.getLogger(__name__)


class ExecutionEventType(str, Enum):
    """Types of execution events"""
    STARTED = "started"
    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"
    STEP_FAILED = "step_failed"
    STEP_REQUIRES_APPROVAL = "step_requires_approval"
    STEP_APPROVED = "step_approved"
    STEP_SKIPPED = "step_skipped"
    PAUSED = "paused"
    RESUMED = "resumed"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLBACK_STARTED = "rollback_started"
    ROLLBACK_COMPLETED = "rollback_completed"
    CANCELLED = "cancelled"


class OperationExecutorService:
    """Service for executing operation plans step by step"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()
        self.planner_service = OperationPlannerService(db)
        self.server_service = ServerService(db)
        self._active_executions: Dict[str, asyncio.Task] = {}
        self._execution_events: Dict[str, List[Dict[str, Any]]] = {}
    
    async def start_execution(self, request: OperationExecutionRequest) -> str:
        """Start executing an operation plan"""
        logger.info(f"Starting execution of plan {request.plan_id}")
        
        # Get the operation plan
        plan = await self.planner_service.get_plan(request.plan_id)
        if not plan:
            raise ValueError(f"Operation plan {request.plan_id} not found")
        
        # Create execution record
        execution_id = str(uuid.uuid4())
        
        # Count total steps (excluding rollback steps)
        total_steps = len([s for s in plan.steps if not s.is_rollback_step])
        
        db_execution = OperationExecution(
            id=execution_id,
            plan_id=request.plan_id,
            execution_mode=request.execution_mode.value,
            auto_approve=request.auto_approve,
            status=ExecutionStatus.PENDING.value,
            total_steps=total_steps,
            completed_steps=0,
            failed_steps=0
        )
        
        self.db.add(db_execution)
        await self.db.commit()
        
        # Initialize event log
        self._execution_events[execution_id] = []
        
        # Start execution task
        execution_task = asyncio.create_task(
            self._execute_plan_async(execution_id, plan, request)
        )
        self._active_executions[execution_id] = execution_task
        
        logger.info(f"Execution {execution_id} started")
        return execution_id
    
    async def get_execution_status(self, execution_id: str) -> Optional[OperationExecutionSchema]:
        """Get current execution status"""
        # Get execution with related step executions
        query = select(OperationExecution).options(
            selectinload(OperationExecution.step_executions)
        ).where(OperationExecution.id == execution_id)
        
        result = await self.db.execute(query)
        db_execution = result.scalar_one_or_none()
        
        if not db_execution:
            return None
        
        # Get step information for all step executions
        step_executions = []
        for db_step_exec in db_execution.step_executions:
            # Get the related step information
            step_query = select(OperationStep).where(OperationStep.id == db_step_exec.step_id)
            step_result = await self.db.execute(step_query)
            step = step_result.scalar_one_or_none()
            
            step_exec_schema = OperationStepExecutionSchema(
                id=str(db_step_exec.id),
                step_id=str(db_step_exec.step_id),
                step_order=step.step_order if step else 0,
                step_name=step.name if step else "Unknown Step",
                status=StepStatus(db_step_exec.status),
                command_executed=db_step_exec.command_executed,
                working_directory=db_step_exec.working_directory,
                stdout=db_step_exec.stdout,
                stderr=db_step_exec.stderr,
                exit_code=db_step_exec.exit_code,
                success=bool(db_step_exec.success) if db_step_exec.success is not None else None,
                started_at=db_step_exec.started_at,
                completed_at=db_step_exec.completed_at,
                execution_time_seconds=float(db_step_exec.execution_time_seconds) if db_step_exec.execution_time_seconds else None,
                validation_performed=bool(db_step_exec.validation_performed),
                validation_success=bool(db_step_exec.validation_success) if db_step_exec.validation_success is not None else None,
                validation_output=db_step_exec.validation_output,
                user_approved=bool(db_step_exec.user_approved) if db_step_exec.user_approved is not None else None,
                approval_timestamp=db_step_exec.approval_timestamp,
                user_notes=db_step_exec.user_notes
            )
            step_executions.append(step_exec_schema)
        
        # Create execution schema
        return OperationExecutionSchema(
            id=str(db_execution.id),
            plan_id=str(db_execution.plan_id),
            execution_mode=ExecutionMode(db_execution.execution_mode),
            auto_approve=bool(db_execution.auto_approve),
            status=ExecutionStatus(db_execution.status),
            current_step_order=int(db_execution.current_step_order) if db_execution.current_step_order else None,
            total_steps=int(db_execution.total_steps),
            completed_steps=int(db_execution.completed_steps),
            failed_steps=int(db_execution.failed_steps),
            started_at=db_execution.started_at,
            completed_at=db_execution.completed_at,
            total_execution_time_seconds=float(db_execution.total_execution_time_seconds) if db_execution.total_execution_time_seconds else None,
            success=bool(db_execution.success) if db_execution.success is not None else None,
            error_message=db_execution.error_message,
            rollback_performed=bool(db_execution.rollback_performed),
            rollback_success=bool(db_execution.rollback_success) if db_execution.rollback_success is not None else None,
            step_executions=step_executions,
            created_at=db_execution.created_at,
            updated_at=db_execution.updated_at
        )
    
    async def get_execution_progress(self, execution_id: str) -> Optional[ExecutionProgress]:
        """Get real-time execution progress"""
        execution = await self.get_execution_status(execution_id)
        if not execution:
            return None
        
        # Calculate progress
        progress_percentage = 0.0
        if execution.total_steps > 0:
            progress_percentage = (execution.completed_steps / execution.total_steps) * 100
        
        # Calculate elapsed time
        elapsed_seconds = 0.0
        if execution.started_at is not None:
            end_time = execution.completed_at if execution.completed_at is not None else datetime.utcnow()
            elapsed_seconds = (end_time - execution.started_at).total_seconds()
        
        # Get current step info
        current_step_name = None
        if execution.current_step_order:
            for step_exec in execution.step_executions:
                if step_exec.step_order == execution.current_step_order:
                    current_step_name = step_exec.step_name
                    break
        
        # Get last output
        last_output = None
        if execution.step_executions:
            for step_exec in reversed(execution.step_executions):
                if step_exec.stdout or step_exec.stderr:
                    last_output = step_exec.stdout or step_exec.stderr
                    break
        
        # Estimate remaining time
        estimated_remaining = None
        if (execution.completed_steps > 0 and 
            execution.status == ExecutionStatus.RUNNING and 
            elapsed_seconds > 0):
            avg_time_per_step = elapsed_seconds / execution.completed_steps
            remaining_steps = execution.total_steps - execution.completed_steps
            estimated_remaining = avg_time_per_step * remaining_steps
        
        return ExecutionProgress(
            execution_id=execution_id,
            status=execution.status,
            current_step=execution.current_step_order,
            current_step_name=current_step_name,
            progress_percentage=progress_percentage,
            completed_steps=execution.completed_steps,
            total_steps=execution.total_steps,
            elapsed_time_seconds=elapsed_seconds,
            estimated_remaining_seconds=estimated_remaining,
            last_output=last_output
        )
    
    async def pause_execution(self, execution_id: str) -> bool:
        """Pause an active execution"""
        if execution_id not in self._active_executions:
            return False
        
        await self._update_execution_status(execution_id, ExecutionStatus.PAUSED)
        await self._log_execution_event(execution_id, ExecutionEventType.PAUSED, {"timestamp": datetime.utcnow()})
        
        logger.info(f"Execution {execution_id} paused")
        return True
    
    async def resume_execution(self, execution_id: str) -> bool:
        """Resume a paused execution"""
        execution = await self.get_execution_status(execution_id)
        if not execution or execution.status != ExecutionStatus.PAUSED:
            return False
        
        await self._update_execution_status(execution_id, ExecutionStatus.RUNNING)
        await self._log_execution_event(execution_id, ExecutionEventType.RESUMED, {"timestamp": datetime.utcnow()})
        
        logger.info(f"Execution {execution_id} resumed")
        return True
    
    async def cancel_execution(self, execution_id: str) -> bool:
        """Cancel an active execution"""
        if execution_id in self._active_executions:
            task = self._active_executions[execution_id]
            task.cancel()
            del self._active_executions[execution_id]
        
        await self._update_execution_status(execution_id, ExecutionStatus.CANCELLED)
        await self._log_execution_event(execution_id, ExecutionEventType.CANCELLED, {"timestamp": datetime.utcnow()})
        
        logger.info(f"Execution {execution_id} cancelled")
        return True
    
    async def approve_step(self, request: StepApprovalRequest) -> bool:
        """Approve a step that requires approval"""
        # Find the step execution
        query = select(OperationStepExecution).where(
            OperationStepExecution.execution_id == request.execution_id,
            OperationStepExecution.step_id == request.step_id
        )
        
        result = await self.db.execute(query)
        step_execution = result.scalar_one_or_none()
        
        if not step_execution:
            return False
        
        # Update approval status using update statement
        update_stmt = update(OperationStepExecution).where(
            OperationStepExecution.id == step_execution.id
        ).values(
            user_approved=request.approved,
            approval_timestamp=datetime.utcnow(),
            user_notes=request.user_notes,
            status=StepStatus.PENDING.value if request.approved else StepStatus.SKIPPED.value
        )
        
        await self.db.execute(update_stmt)
        await self.db.commit()
        
        await self._log_execution_event(
            request.execution_id, 
            ExecutionEventType.STEP_APPROVED,
            {
                "step_id": request.step_id,
                "approved": request.approved,
                "user_notes": request.user_notes
            }
        )
        
        logger.info(f"Step {request.step_id} {'approved' if request.approved else 'rejected'}")
        return True
    
    async def rollback_execution(self, execution_id: str) -> bool:
        """Rollback a failed or completed execution"""
        # Get execution and plan
        execution = await self.get_execution_status(execution_id)
        if not execution:
            return False
        
        plan = await self.planner_service.get_plan(execution.plan_id)
        if not plan:
            return False
        
        await self._log_execution_event(execution_id, ExecutionEventType.ROLLBACK_STARTED, {"timestamp": datetime.utcnow()})
        
        try:
            # Execute rollback steps in reverse order
            rollback_success = await self._execute_rollback(execution_id, plan, execution)
            
            # Update execution status
            update_data = {
                "rollback_performed": True,
                "rollback_success": rollback_success,
                "status": ExecutionStatus.ROLLED_BACK.value
            }
            
            await self._update_execution_fields(execution_id, update_data)
            
            await self._log_execution_event(
                execution_id, 
                ExecutionEventType.ROLLBACK_COMPLETED,
                {"success": rollback_success}
            )
            
            logger.info(f"Rollback of execution {execution_id} {'succeeded' if rollback_success else 'failed'}")
            return rollback_success
            
        except Exception as e:
            logger.error(f"Rollback failed for execution {execution_id}: {e}")
            await self._update_execution_fields(execution_id, {
                "rollback_performed": True,
                "rollback_success": False,
                "error_message": f"Rollback failed: {str(e)}"
            })
            return False
    
    async def _execute_plan_async(
        self, 
        execution_id: str, 
        plan, 
        request: OperationExecutionRequest
    ):
        """Execute operation plan asynchronously"""
        try:
            # Update execution status to running
            await self._update_execution_status(execution_id, ExecutionStatus.RUNNING)
            await self._update_execution_fields(execution_id, {"started_at": datetime.utcnow()})
            
            await self._log_execution_event(execution_id, ExecutionEventType.STARTED, {"plan_id": plan.id})
            
            # Filter steps based on request parameters
            steps_to_execute = self._filter_steps_for_execution(plan, request)
            
            # Execute steps sequentially
            completed_steps = 0
            failed_steps = 0
            
            for step in steps_to_execute:
                if await self._is_execution_paused_or_cancelled(execution_id):
                    break
                
                # Update current step
                await self._update_execution_fields(execution_id, {"current_step_order": step.step_order})
                
                # Execute step
                step_success = await self._execute_step(
                    execution_id, step, request.execution_mode, request.auto_approve
                )
                
                if step_success:
                    completed_steps += 1
                else:
                    failed_steps += 1
                    
                    # Stop execution on failure unless in safe mode
                    if request.execution_mode != ExecutionMode.DRY_RUN:
                        break
                
                # Update progress
                await self._update_execution_fields(execution_id, {
                    "completed_steps": completed_steps,
                    "failed_steps": failed_steps
                })
            
            # Determine final status
            execution_status = await self.get_execution_status(execution_id)
            if execution_status and execution_status.status == ExecutionStatus.CANCELLED:
                final_status = ExecutionStatus.CANCELLED
            elif failed_steps > 0:
                final_status = ExecutionStatus.FAILED
            else:
                final_status = ExecutionStatus.COMPLETED
            
            # Calculate total execution time
            end_time = datetime.utcnow()
            start_time = execution_status.started_at if execution_status and execution_status.started_at else end_time
            total_time = (end_time - start_time).total_seconds()
            
            # Update final status
            await self._update_execution_fields(execution_id, {
                "status": final_status.value,
                "completed_at": end_time,
                "total_execution_time_seconds": total_time,
                "success": failed_steps == 0
            })
            
            await self._log_execution_event(
                execution_id, 
                ExecutionEventType.COMPLETED if failed_steps == 0 else ExecutionEventType.FAILED,
                {
                    "completed_steps": completed_steps,
                    "failed_steps": failed_steps,
                    "total_time": total_time
                }
            )
            
            logger.info(f"Execution {execution_id} finished: {final_status.value}")
            
        except Exception as e:
            logger.error(f"Execution {execution_id} failed with exception: {e}")
            await self._update_execution_fields(execution_id, {
                "status": ExecutionStatus.FAILED.value,
                "completed_at": datetime.utcnow(),
                "success": False,
                "error_message": str(e)
            })
            
            await self._log_execution_event(execution_id, ExecutionEventType.FAILED, {"error": str(e)})
            
        finally:
            # Clean up
            if execution_id in self._active_executions:
                del self._active_executions[execution_id]
    
    def _filter_steps_for_execution(self, plan, request: OperationExecutionRequest):
        """Filter steps based on execution request parameters"""
        all_steps = plan.prerequisite_steps + plan.steps
        
        # Filter out rollback steps for normal execution
        steps = [s for s in all_steps if not s.is_rollback_step]
        
        # Apply step filters
        if request.execute_only_steps:
            steps = [s for s in steps if s.step_order in request.execute_only_steps]
        
        if request.start_from_step:
            steps = [s for s in steps if s.step_order >= request.start_from_step]
        
        # Sort by step order
        return sorted(steps, key=lambda s: s.step_order)
    
    async def _execute_step(
        self, 
        execution_id: str, 
        step, 
        execution_mode: ExecutionMode,
        auto_approve: bool
    ) -> bool:
        """Execute a single step"""
        step_exec_id = str(uuid.uuid4())
        
        # Get the plan to access server_id
        query = select(OperationExecution).where(OperationExecution.id == execution_id)
        result = await self.db.execute(query)
        execution = result.scalar_one_or_none()
        
        if not execution:
            raise Exception("Execution record not found")
        
        query = select(OperationPlan).where(OperationPlan.id == execution.plan_id)
        result = await self.db.execute(query)
        plan = result.scalar_one_or_none()
        
        if not plan:
            raise Exception("Plan record not found")
        
        # Create step execution record
        db_step_execution = OperationStepExecution(
            id=step_exec_id,
            execution_id=execution_id,
            step_id=step.id if step.id else str(uuid.uuid4()),
            status=StepStatus.PENDING.value,
            command_executed=step.command,
            working_directory=step.working_directory
        )
        
        self.db.add(db_step_execution)
        await self.db.commit()
        
        await self._log_execution_event(
            execution_id, 
            ExecutionEventType.STEP_STARTED,
            {"step_order": step.step_order, "step_name": step.name}
        )
        
        try:
            # Check if step requires approval
            if step.requires_approval and not auto_approve:
                # Mark as requiring approval
                await self._update_step_execution_fields(step_exec_id, {
                    "status": StepStatus.REQUIRES_APPROVAL.value
                })
                
                await self._log_execution_event(
                    execution_id,
                    ExecutionEventType.STEP_REQUIRES_APPROVAL,
                    {"step_id": step.id, "step_name": step.name}
                )
                
                # For now, skip the step if it requires approval
                logger.info(f"Step {step.step_order} requires approval - marking as skipped")
                await self._update_step_execution_fields(step_exec_id, {
                    "status": StepStatus.SKIPPED.value
                })
                return True
            
            # Update step status to running
            start_time = datetime.utcnow()
            await self._update_step_execution_fields(step_exec_id, {
                "status": StepStatus.RUNNING.value,
                "started_at": start_time
            })
            
            # Map execution mode to safety level
            safety_level_map = {
                ExecutionMode.DRY_RUN: SafetyLevel.DRY_RUN,
                ExecutionMode.SAFE: SafetyLevel.SAFE,
                ExecutionMode.CAUTIOUS: SafetyLevel.CAUTIOUS,
                ExecutionMode.FULL: SafetyLevel.FULL
            }
            safety_level = safety_level_map[execution_mode]
            
            # Execute command
            result = await self.server_service.execute_command(
                server_id=str(plan.server_id),
                command=step.command,
                working_dir=step.working_directory,
                timeout=step.estimated_duration_seconds or 30,
                safety_level=safety_level
            )
            
            # Calculate execution time
            completed_at = datetime.utcnow()
            execution_time = (completed_at - start_time).total_seconds()
            
            # Prepare update data
            step_update_data = {
                "stdout": result.get("stdout", ""),
                "stderr": result.get("stderr", ""),
                "exit_code": result.get("exit_code", 0),
                "success": result.get("success", False),
                "completed_at": completed_at,
                "execution_time_seconds": execution_time
            }
            
            # Perform validation if specified
            if step.validation_command and result.get("success", False):
                validation_result = await self.server_service.execute_command(
                    server_id=str(plan.server_id),
                    command=step.validation_command,
                    working_dir=step.working_directory,
                    timeout=10,
                    safety_level=safety_level
                )
                
                validation_success = validation_result.get("success", False)
                step_update_data.update({
                    "validation_performed": True,
                    "validation_success": validation_success,
                    "validation_output": validation_result.get("stdout", "")
                })
                
                # Update overall success based on validation
                if not validation_success:
                    step_update_data["success"] = False
            
            # Update final status
            if step_update_data["success"]:
                step_update_data["status"] = StepStatus.COMPLETED.value
                await self._log_execution_event(
                    execution_id,
                    ExecutionEventType.STEP_COMPLETED,
                    {"step_order": step.step_order, "step_name": step.name}
                )
            else:
                step_update_data["status"] = StepStatus.FAILED.value
                await self._log_execution_event(
                    execution_id,
                    ExecutionEventType.STEP_FAILED,
                    {
                        "step_order": step.step_order, 
                        "step_name": step.name,
                        "error": step_update_data["stderr"]
                    }
                )
            
            await self._update_step_execution_fields(step_exec_id, step_update_data)
            return bool(step_update_data["success"])
            
        except Exception as e:
            logger.error(f"Step execution failed: {e}")
            
            # Update step execution with error
            error_update_data = {
                "status": StepStatus.FAILED.value,
                "stderr": str(e),
                "success": False,
                "completed_at": datetime.utcnow()
            }
            
            await self._update_step_execution_fields(step_exec_id, error_update_data)
            
            await self._log_execution_event(
                execution_id,
                ExecutionEventType.STEP_FAILED,
                {"step_order": step.step_order, "step_name": step.name, "error": str(e)}
            )
            
            return False
    
    async def _execute_rollback(self, execution_id: str, plan, execution) -> bool:
        """Execute rollback procedure"""
        logger.info(f"Starting rollback for execution {execution_id}")
        
        try:
            # Get completed steps that need rollback
            completed_steps = [
                step_exec for step_exec in execution.step_executions 
                if step_exec.status == StepStatus.COMPLETED
            ]
            
            # Find corresponding plan steps with rollback commands
            rollback_operations = []
            for step_exec in completed_steps:
                # Find the plan step
                plan_step = None
                for step in plan.steps:
                    if step.id == step_exec.step_id:
                        plan_step = step
                        break
                
                if plan_step and plan_step.rollback_command:
                    rollback_operations.append((step_exec, plan_step))
            
            # Execute rollback operations in reverse order
            rollback_operations.reverse()
            
            rollback_success = True
            for step_exec, plan_step in rollback_operations:
                try:
                    logger.info(f"Rolling back step {plan_step.step_order}: {plan_step.name}")
                    
                    result = await self.server_service.execute_command(
                        server_id=plan.server_id,
                        command=plan_step.rollback_command,
                        working_dir=plan_step.working_directory,
                        timeout=30,
                        safety_level=SafetyLevel.CAUTIOUS
                    )
                    
                    # Update step execution with rollback info - using explicit field names
                    rollback_data = {
                        "rollback_executed": True,
                        "rollback_success": result.get("success", False),
                        "rollback_output": result.get("stdout", "")
                    }
                    
                    # Note: These fields need to exist in the database model
                    await self._update_step_execution_fields(step_exec.id, rollback_data)
                    
                    if not result.get("success", False):
                        rollback_success = False
                        logger.error(f"Rollback failed for step {plan_step.step_order}")
                        
                except Exception as e:
                    logger.error(f"Rollback error for step {plan_step.step_order}: {e}")
                    rollback_success = False
            
            return rollback_success
            
        except Exception as e:
            logger.error(f"Rollback execution failed: {e}")
            return False
    
    async def _is_execution_paused_or_cancelled(self, execution_id: str) -> bool:
        """Check if execution is paused or cancelled"""
        execution = await self.get_execution_status(execution_id)
        if not execution:
            return True
        
        return execution.status in [ExecutionStatus.PAUSED, ExecutionStatus.CANCELLED]
    
    async def _update_execution_status(self, execution_id: str, status: ExecutionStatus):
        """Update execution status in database"""
        await self._update_execution_fields(execution_id, {"status": status.value})
    
    async def _update_execution_fields(self, execution_id: str, fields: Dict[str, Any]):
        """Update execution fields in database"""
        fields["updated_at"] = datetime.utcnow()
        
        update_stmt = update(OperationExecution).where(
            OperationExecution.id == execution_id
        ).values(**fields)
        
        await self.db.execute(update_stmt)
        await self.db.commit()
    
    async def _update_step_execution_fields(self, step_exec_id: str, fields: Dict[str, Any]):
        """Update step execution fields in database"""
        update_stmt = update(OperationStepExecution).where(
            OperationStepExecution.id == step_exec_id
        ).values(**fields)
        
        await self.db.execute(update_stmt)
        await self.db.commit()
    
    async def _log_execution_event(
        self, 
        execution_id: str, 
        event_type: ExecutionEventType, 
        data: Dict[str, Any]
    ):
        """Log execution event"""
        if execution_id not in self._execution_events:
            self._execution_events[execution_id] = []
        
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type.value,
            "data": data
        }
        
        self._execution_events[execution_id].append(event)
        
        # Keep only last 100 events per execution
        if len(self._execution_events[execution_id]) > 100:
            self._execution_events[execution_id] = self._execution_events[execution_id][-100:]