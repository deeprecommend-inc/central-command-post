from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime

from ..models.database import get_db, Run, Account, KillSwitch, RunStatusEnum, PlatformEnum, EngineTypeEnum
from ..services.redis_service import redis_service
from ..services.observability import ObservabilityThreshold
from ..services.audit_service import audit_log


router = APIRouter()


class CreateRunRequest(BaseModel):
    account_id: int
    platform: str
    engine: str = "api_fast"
    schedule: Dict[str, Any]
    rate_config: Dict[str, Any]
    observability_config: Optional[Dict[str, Any]] = None
    prompt_config: Dict[str, Any]
    custom_prompt: Optional[str] = None
    approval_required: bool = True


class UpdateRunRequest(BaseModel):
    status: Optional[str] = None
    schedule: Optional[Dict[str, Any]] = None
    rate_config: Optional[Dict[str, Any]] = None


@router.post("/")
async def create_run(
    data: CreateRunRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new run
    """
    # Verify account exists
    account_result = await db.execute(
        select(Account).where(Account.id == data.account_id)
    )
    account = account_result.scalar_one_or_none()

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    # Default observability config
    if not data.observability_config:
        data.observability_config = ObservabilityThreshold().to_dict()

    # Create run
    run = Run(
        account_id=data.account_id,
        platform=PlatformEnum[data.platform.upper()],
        engine=EngineTypeEnum[data.engine.upper()],
        schedule_json=data.schedule,
        observability_json=data.observability_config,
        prompt_json=data.prompt_config,
        rate_config=data.rate_config,
        custom_prompt=data.custom_prompt,
        approval_required=data.approval_required,
        created_by=1,  # TODO: Get from authenticated user
        status=RunStatusEnum.PENDING
    )

    db.add(run)
    await db.commit()
    await db.refresh(run)

    # Audit log
    await audit_log(
        actor_user_id=1,
        operation="create_run",
        payload={
            "run_id": run.id,
            "platform": data.platform,
            "engine": data.engine,
        },
        session=db,
        ip_address=request.client.host
    )

    return {
        "success": True,
        "run_id": run.id,
        "status": run.status.value
    }


@router.get("/{run_id}")
async def get_run(
    run_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get run details
    """
    result = await db.execute(
        select(Run).where(Run.id == run_id)
    )
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    return {
        "id": run.id,
        "account_id": run.account_id,
        "platform": run.platform.value,
        "engine": run.engine.value,
        "status": run.status.value,
        "schedule": run.schedule_json,
        "rate_config": run.rate_config,
        "observability_config": run.observability_json,
        "approval_required": run.approval_required,
        "created_at": run.created_at.isoformat(),
        "updated_at": run.updated_at.isoformat() if run.updated_at else None,
    }


@router.get("/")
async def list_runs(
    platform: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """
    List runs with filters
    """
    query = select(Run)

    if platform:
        query = query.where(Run.platform == PlatformEnum[platform.upper()])

    if status:
        query = query.where(Run.status == RunStatusEnum[status.upper()])

    query = query.order_by(Run.created_at.desc()).limit(limit)

    result = await db.execute(query)
    runs = result.scalars().all()

    return {
        "runs": [
            {
                "id": run.id,
                "platform": run.platform.value,
                "engine": run.engine.value,
                "status": run.status.value,
                "created_at": run.created_at.isoformat(),
            }
            for run in runs
        ],
        "count": len(runs)
    }


@router.patch("/{run_id}")
async def update_run(
    run_id: int,
    data: UpdateRunRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Update run
    """
    result = await db.execute(
        select(Run).where(Run.id == run_id)
    )
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Update fields
    if data.status:
        run.status = RunStatusEnum[data.status.upper()]

    if data.schedule:
        run.schedule_json = data.schedule

    if data.rate_config:
        run.rate_config = data.rate_config

    await db.commit()

    # Audit log
    await audit_log(
        actor_user_id=1,
        operation="update_run",
        payload={
            "run_id": run_id,
            "changes": data.dict(exclude_none=True),
        },
        session=db,
        ip_address=request.client.host
    )

    return {
        "success": True,
        "run_id": run_id
    }


@router.post("/{run_id}/kill")
async def kill_run(
    run_id: int,
    reason: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Activate kill switch for a run
    """
    result = await db.execute(
        select(Run).where(Run.id == run_id)
    )
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Check if kill switch already exists
    ks_result = await db.execute(
        select(KillSwitch).where(KillSwitch.run_id == run_id)
    )
    kill_switch = ks_result.scalar_one_or_none()

    if kill_switch:
        kill_switch.is_active = True
        kill_switch.triggered_at = datetime.utcnow()
        kill_switch.triggered_by = 1  # TODO: Get from authenticated user
        kill_switch.reason = reason
    else:
        kill_switch = KillSwitch(
            run_id=run_id,
            is_active=True,
            triggered_at=datetime.utcnow(),
            triggered_by=1,
            reason=reason
        )
        db.add(kill_switch)

    # Update run status
    run.status = RunStatusEnum.ABORTED

    await db.commit()

    # Audit log
    await audit_log(
        actor_user_id=1,
        operation="kill_run",
        payload={
            "run_id": run_id,
            "reason": reason,
        },
        session=db,
        ip_address=request.client.host
    )

    return {
        "success": True,
        "message": "Run killed",
        "run_id": run_id
    }


@router.post("/{run_id}/enqueue")
async def enqueue_run_jobs(
    run_id: int,
    jobs: List[Dict[str, Any]],
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Enqueue jobs for a run
    """
    result = await db.execute(
        select(Run).where(Run.id == run_id)
    )
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Enqueue each job
    for job in jobs:
        job["run_id"] = run_id
        await redis_service.enqueue_job("execution_queue", job)

    # Update run status
    run.status = RunStatusEnum.RUNNING
    await db.commit()

    return {
        "success": True,
        "run_id": run_id,
        "jobs_enqueued": len(jobs)
    }
