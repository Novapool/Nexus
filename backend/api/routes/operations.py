"""
Operation planning and execution API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, WebSocket
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import asyncio
from backend.config.database import get_db
from backend.models.operation_schemas import (
    OperationPlanRequest, OperationPlanResponse, OperationPlanSchema,
    OperationExecutionRequest, OperationExecutionResponse, OperationExecutionSchema,
    ExecutionProgress, StepApprovalRequest, OperationType, ExecutionStatus,
    PlanValidationResult, OperationTemplateSchema, OperationTemplateResponse,
    ExecutionMode
)
from backend.services.operation_planner_service import OperationPlannerService
from backend.services.operation_executor_service import OperationExecutorService
from backend.services.server_service import ServerService
from backend.core.exceptions import ServerNotFoundError, AIServiceError
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


# Operation Planning Endpoints

@router.post("/plans", response_model=OperationPlanResponse)
async def create_operation_plan(
    request: OperationPlanRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Generate a new operation plan from natural language request"""
    planner_service = OperationPlannerService(db)
    
    try:
        # Validate server exists
        server_service = ServerService(db)
        server = await server_service.get_server(request.server_id)
        if not server:
            raise ServerNotFoundError(request.server_id)
        
        # Generate plan
        plan = await planner_service.generate_plan(request)
        
        # Save plan to database
        plan_id = await planner_service.save_plan(plan)
        plan.id = plan_id
        
        logger.info(f"Created operation plan {plan_id} for server {request.server_id}")
        
        return OperationPlanResponse(**plan.dict())
        
    except ServerNotFoundError:
        raise
    except AIServiceError as e:
        logger.error(f"Plan generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error creating plan: {e}")
        raise HTTPException(status_code=500, detail="Failed to create operation plan")


@router.get("/plans", response_model=List[OperationPlanResponse])
async def list_operation_plans(
    server_id: Optional[str] = None,
    operation_type: Optional[OperationType] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """List operation plans with optional filters"""
    planner_service = OperationPlannerService(db)
    
    try:
        plans = await planner_service.list_plans(
            server_id=server_id,
            operation_type=operation_type,
            skip=skip,
            limit=limit
        )
        
        return [OperationPlanResponse(**plan.dict()) for plan in plans]
        
    except Exception as e:
        logger.error(f"Failed to list plans: {e}")
        raise HTTPException(status_code=500, detail="Failed to list operation plans")


@router.get("/plans/{plan_id}", response_model=OperationPlanResponse)
async def get_operation_plan(
    plan_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get operation plan by ID"""
    planner_service = OperationPlannerService(db)
    
    plan = await planner_service.get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Operation plan {plan_id} not found")
    
    return OperationPlanResponse(**plan.dict())


@router.post("/plans/{plan_id}/validate", response_model=PlanValidationResult)
async def validate_operation_plan(
    plan_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Validate operation plan for safety and feasibility"""
    planner_service = OperationPlannerService(db)
    server_service = ServerService(db)
    
    try:
        # Get plan
        plan = await planner_service.get_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail=f"Operation plan {plan_id} not found")
        
        # Get server context
        server_context = await server_service.get_server_context(plan.server_id)
        
        # Validate plan
        validation_result = await planner_service.validate_plan(plan, server_context)
        
        return validation_result
        
    except Exception as e:
        logger.error(f"Plan validation failed: {e}")
        raise HTTPException(status_code=500, detail="Plan validation failed")


@router.delete("/plans/{plan_id}")
async def delete_operation_plan(
    plan_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Delete operation plan"""
    # Implementation would delete the plan from database
    # For now, just return success
    return {"message": f"Operation plan {plan_id} deleted successfully"}


# Operation Execution Endpoints

@router.post("/execute", response_model=dict)
async def start_operation_execution(
    request: OperationExecutionRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Start executing an operation plan"""
    executor_service = OperationExecutorService(db)
    
    try:
        # Start execution
        execution_id = await executor_service.start_execution(request)
        
        return {
            "execution_id": execution_id,
            "status": "started",
            "message": f"Operation execution {execution_id} started"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to start execution: {e}")
        raise HTTPException(status_code=500, detail="Failed to start operation execution")


@router.get("/executions/{execution_id}", response_model=OperationExecutionResponse)
async def get_execution_status(
    execution_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get detailed execution status"""
    executor_service = OperationExecutorService(db)
    
    execution = await executor_service.get_execution_status(execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail=f"Execution {execution_id} not found")
    
    return OperationExecutionResponse(**execution.dict())


@router.get("/executions/{execution_id}/progress", response_model=ExecutionProgress)
async def get_execution_progress(
    execution_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get real-time execution progress"""
    executor_service = OperationExecutorService(db)
    
    progress = await executor_service.get_execution_progress(execution_id)
    if not progress:
        raise HTTPException(status_code=404, detail=f"Execution {execution_id} not found")
    
    return progress


@router.post("/executions/{execution_id}/pause")
async def pause_execution(
    execution_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Pause an active execution"""
    executor_service = OperationExecutorService(db)
    
    success = await executor_service.pause_execution(execution_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Execution {execution_id} not found or cannot be paused")
    
    return {"message": f"Execution {execution_id} paused successfully"}


@router.post("/executions/{execution_id}/resume")
async def resume_execution(
    execution_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Resume a paused execution"""
    executor_service = OperationExecutorService(db)
    
    success = await executor_service.resume_execution(execution_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Execution {execution_id} not found or cannot be resumed")
    
    return {"message": f"Execution {execution_id} resumed successfully"}


@router.post("/executions/{execution_id}/cancel")
async def cancel_execution(
    execution_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Cancel an active execution"""
    executor_service = OperationExecutorService(db)
    
    success = await executor_service.cancel_execution(execution_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Execution {execution_id} not found")
    
    return {"message": f"Execution {execution_id} cancelled successfully"}


@router.post("/executions/{execution_id}/rollback")
async def rollback_execution(
    execution_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Rollback a failed or completed execution"""
    executor_service = OperationExecutorService(db)
    
    try:
        # Start rollback in background
        background_tasks.add_task(executor_service.rollback_execution, execution_id)
        
        return {"message": f"Rollback of execution {execution_id} started"}
        
    except Exception as e:
        logger.error(f"Failed to start rollback: {e}")
        raise HTTPException(status_code=500, detail="Failed to start rollback")


@router.post("/executions/{execution_id}/approve-step")
async def approve_step(
    execution_id: str,
    request: StepApprovalRequest,
    db: AsyncSession = Depends(get_db)
):
    """Approve or reject a step that requires approval"""
    executor_service = OperationExecutorService(db)
    
    # Validate execution_id matches
    if execution_id != request.execution_id:
        raise HTTPException(status_code=400, detail="Execution ID mismatch")
    
    success = await executor_service.approve_step(request)
    if not success:
        raise HTTPException(status_code=404, detail="Step execution not found")
    
    action = "approved" if request.approved else "rejected"
    return {"message": f"Step {request.step_id} {action} successfully"}


# Operation Templates Endpoints

@router.get("/templates", response_model=List[OperationTemplateResponse])
async def list_operation_templates(
    category: Optional[str] = None,
    os_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """List available operation templates"""
    # Implementation would list templates from database
    # For now, return empty list
    return []


@router.post("/templates", response_model=OperationTemplateResponse)
async def create_operation_template(
    template: OperationTemplateSchema,
    db: AsyncSession = Depends(get_db)
):
    """Create a new operation template"""
    # Implementation would save template to database
    # For now, return the template with an ID
    template_dict = template.dict()
    template_dict["id"] = "template_123"
    return OperationTemplateResponse(**template_dict)


@router.get("/templates/{template_id}", response_model=OperationTemplateResponse)
async def get_operation_template(
    template_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get operation template by ID"""
    # Implementation would get template from database
    raise HTTPException(status_code=404, detail=f"Template {template_id} not found")


# Utility Endpoints

@router.post("/quick-execute")
async def quick_execute_operation(
    prompt: str,
    server_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    execution_mode: str = "cautious",
    auto_approve: bool = False
):
    """Quick operation: generate plan and execute immediately"""
    try:
        # Generate plan
        planner_service = OperationPlannerService(db)
        plan_request = OperationPlanRequest(
            prompt=prompt,
            server_id=server_id,
            operation_type=None,
            context=None,
            save_as_template=False,
            template_name=None
        )
        
        plan = await planner_service.generate_plan(plan_request)
        plan_id = await planner_service.save_plan(plan)
        
        # Start execution
        executor_service = OperationExecutorService(db)
        execution_request = OperationExecutionRequest(
            plan_id=plan_id,
            execution_mode=ExecutionMode(execution_mode),
            auto_approve=auto_approve,
            start_from_step=None,
            execute_only_steps=None
        )
        
        execution_id = await executor_service.start_execution(execution_request)
        
        return {
            "plan_id": plan_id,
            "execution_id": execution_id,
            "message": "Operation plan generated and execution started"
        }
        
    except Exception as e:
        logger.error(f"Quick execute failed: {e}")
        raise HTTPException(status_code=500, detail=f"Quick execute failed: {str(e)}")


@router.get("/operation-types")
async def get_operation_types():
    """Get available operation types and their descriptions"""
    return {
        "operation_types": [
            {
                "type": "simple",
                "description": "Basic operations (3-5 steps) like installing packages or creating files",
                "examples": ["Install Docker", "Create user account", "Update system packages"]
            },
            {
                "type": "complex", 
                "description": "Multi-component setups (6-12 steps) like web servers with SSL",
                "examples": ["Setup web server with SSL", "Configure database server", "Install monitoring stack"]
            },
            {
                "type": "advanced",
                "description": "Complete system setups (13+ steps) like full deployments",
                "examples": ["Deploy full LAMP stack", "Setup Kubernetes cluster", "Configure security hardening"]
            }
        ]
    }


@router.get("/execution-modes")
async def get_execution_modes():
    """Get available execution modes and their descriptions"""
    return {
        "execution_modes": [
            {
                "mode": "dry_run",
                "description": "Validate commands but don't execute them",
                "risk": "none"
            },
            {
                "mode": "safe", 
                "description": "Execute only commands marked as safe",
                "risk": "low"
            },
            {
                "mode": "cautious",
                "description": "Execute commands with approval required for risky operations",
                "risk": "medium"
            },
            {
                "mode": "full",
                "description": "Execute all validated commands without additional prompts",
                "risk": "high"
            }
        ]
    }


# Advanced Features

@router.post("/analyze-prompt")
async def analyze_operation_prompt(
    prompt: str,
    server_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Analyze a natural language prompt and provide operation insights"""
    try:
        planner_service = OperationPlannerService(db)
        server_service = ServerService(db)
        
        # Get server context
        server_context = await server_service.get_server_context(server_id)
        
        # Classify operation
        operation_type = await planner_service._classify_operation(prompt, server_context)
        
        # Estimate complexity
        complexity_info = {
            "simple": {"steps": "3-5", "duration": "1-5 minutes", "risk": "low"},
            "complex": {"steps": "6-12", "duration": "5-20 minutes", "risk": "medium"}, 
            "advanced": {"steps": "13+", "duration": "20+ minutes", "risk": "high"}
        }
        
        return {
            "prompt": prompt,
            "operation_type": operation_type.value,
            "estimated_complexity": complexity_info[operation_type.value],
            "server_compatibility": {
                "os_type": server_context.get("os_type"),
                "package_manager": server_context.get("capabilities", {}).get("package_manager"),
                "suitable": True  # Would include actual compatibility checks
            },
            "recommendations": [
                f"This appears to be a {operation_type.value} operation",
                f"Estimated {complexity_info[operation_type.value]['steps']} steps",
                f"Consider using {operation_type.value} reasoning level"
            ]
        }
        
    except Exception as e:
        logger.error(f"Prompt analysis failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to analyze prompt")


@router.get("/stats/executions")
async def get_execution_statistics(
    server_id: Optional[str] = None,
    days: int = 30,
    db: AsyncSession = Depends(get_db)
):
    """Get execution statistics and success rates"""
    # Implementation would query database for statistics
    # For now, return mock data
    return {
        "total_executions": 42,
        "successful_executions": 38,
        "failed_executions": 4,
        "success_rate": 90.5,
        "avg_execution_time": 245.7,
        "most_common_operations": [
            {"type": "simple", "count": 25},
            {"type": "complex", "count": 15},
            {"type": "advanced", "count": 2}
        ],
        "period_days": days
    }


@router.post("/operations/batch")
async def batch_operation_execution(
    operations: List[dict],
    server_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    execution_mode: str = "cautious"
):
    """Execute multiple operations in sequence"""
    try:
        execution_ids = []
        
        for i, operation in enumerate(operations):
            prompt = operation.get("prompt", "")
            if not prompt:
                continue
            
            # Generate plan
            planner_service = OperationPlannerService(db)
            plan_request = OperationPlanRequest(
                prompt=prompt,
                server_id=server_id,
                operation_type=None,
                context=None,
                save_as_template=False,
                template_name=None
            )
            
            plan = await planner_service.generate_plan(plan_request)
            plan_id = await planner_service.save_plan(plan)
            
            # Queue execution (would implement proper queuing)
            executor_service = OperationExecutorService(db)
            execution_request = OperationExecutionRequest(
                plan_id=plan_id,
                execution_mode=ExecutionMode(execution_mode),
                auto_approve=operation.get("auto_approve", False),
                start_from_step=None,
                execute_only_steps=None
            )
            
            execution_id = await executor_service.start_execution(execution_request)
            execution_ids.append({
                "operation_index": i,
                "prompt": prompt,
                "plan_id": plan_id,
                "execution_id": execution_id
            })
        
        return {
            "batch_id": f"batch_{len(execution_ids)}_{server_id}",
            "operations": execution_ids,
            "message": f"Started {len(execution_ids)} operations"
        }
        
    except Exception as e:
        logger.error(f"Batch execution failed: {e}")
        raise HTTPException(status_code=500, detail=f"Batch execution failed: {str(e)}")


# WebSocket endpoint for real-time updates (placeholder)
@router.websocket("/executions/{execution_id}/ws")
async def execution_websocket(websocket: WebSocket, execution_id: str):
    """WebSocket endpoint for real-time execution updates"""
    await websocket.accept()
    
    try:
        await websocket.send_text(f"Connected to execution {execution_id}")
        await websocket.send_text("Real-time updates not fully implemented yet")
        
        while True:
            # In a real implementation, this would send progress updates
            await asyncio.sleep(5)
            await websocket.send_text(f"Heartbeat for execution {execution_id}")
            
    except Exception as e:
        logger.error(f"WebSocket error for execution {execution_id}: {e}")
    finally:
        await websocket.close()
