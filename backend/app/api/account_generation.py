from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
from typing import Optional
import secrets
import string

from ..models.database import (
    get_db,
    AccountGenerationTask,
    GeneratedAccount,
    PlatformEnum,
    AccountGenStatusEnum,
    StatusEnum
)
from ..services.audit_service import audit_log

router = APIRouter()


def generate_username(pattern: str, index: int) -> str:
    """
    Generate username based on pattern
    Pattern examples:
    - "user_{}" -> user_1, user_2, ...
    - "test_{:04d}" -> test_0001, test_0002, ...
    - "random" -> random string
    """
    if pattern == "random":
        return ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(12))
    return pattern.format(index)


def generate_email(domain: str, username: str) -> str:
    """Generate email address"""
    return f"{username}@{domain}"


def generate_password(length: int = 16) -> str:
    """Generate secure random password"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))


@router.post("/account-generation/tasks")
async def create_generation_task(
    platform: str,
    target_count: int,
    username_pattern: str = "user_{}",
    email_domain: str = "temp-mail.com",
    phone_provider: Optional[str] = None,
    proxy_list: list[str] = [],
    use_residential_proxy: bool = True,
    headless: bool = True,
    request: Request = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Create account generation task
    """
    if target_count < 1 or target_count > 100:
        raise HTTPException(
            status_code=400,
            detail="target_count must be between 1 and 100"
        )

    # Validate platform
    try:
        platform_enum = PlatformEnum[platform.upper()]
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Invalid platform: {platform}")

    # Create generation task
    task = AccountGenerationTask(
        platform=platform_enum,
        target_count=target_count,
        generation_config={
            "username_pattern": username_pattern,
            "email_domain": email_domain,
            "phone_provider": phone_provider,
        },
        proxy_list=proxy_list,
        use_residential_proxy=use_residential_proxy,
        headless=headless,
        status=AccountGenStatusEnum.PENDING,
        created_by=1  # TODO: Get from authenticated user
    )

    db.add(task)
    await db.commit()
    await db.refresh(task)

    # Audit log
    if request:
        await audit_log(
            actor_user_id=1,
            operation="create_account_generation_task",
            payload={
                "task_id": task.id,
                "platform": platform,
                "target_count": target_count,
            },
            session=db,
            ip_address=request.client.host if request.client else None
        )

    return {
        "success": True,
        "task_id": task.id,
        "status": task.status.value
    }


@router.get("/account-generation/tasks")
async def list_generation_tasks(
    platform: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """
    List account generation tasks
    """
    query = select(AccountGenerationTask).order_by(AccountGenerationTask.created_at.desc())

    if platform:
        try:
            platform_enum = PlatformEnum[platform.upper()]
            query = query.where(AccountGenerationTask.platform == platform_enum)
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Invalid platform: {platform}")

    if status:
        try:
            status_enum = AccountGenStatusEnum[status.upper()]
            query = query.where(AccountGenerationTask.status == status_enum)
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    query = query.limit(limit)
    result = await db.execute(query)
    tasks = result.scalars().all()

    return {
        "tasks": [
            {
                "id": task.id,
                "platform": task.platform.value,
                "target_count": task.target_count,
                "completed_count": task.completed_count,
                "failed_count": task.failed_count,
                "status": task.status.value,
                "generation_config": task.generation_config,
                "proxy_list": task.proxy_list,
                "use_residential_proxy": task.use_residential_proxy,
                "headless": task.headless,
                "error_message": task.error_message,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "started_at": task.started_at.isoformat() if task.started_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            }
            for task in tasks
        ]
    }


@router.get("/account-generation/tasks/{task_id}")
async def get_generation_task(
    task_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get specific generation task with generated accounts
    """
    result = await db.execute(
        select(AccountGenerationTask).where(AccountGenerationTask.id == task_id)
    )
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Get generated accounts for this task
    accounts_result = await db.execute(
        select(GeneratedAccount).where(GeneratedAccount.task_id == task_id)
    )
    accounts = accounts_result.scalars().all()

    return {
        "task": {
            "id": task.id,
            "platform": task.platform.value,
            "target_count": task.target_count,
            "completed_count": task.completed_count,
            "failed_count": task.failed_count,
            "status": task.status.value,
            "generation_config": task.generation_config,
            "error_message": task.error_message,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        },
        "accounts": [
            {
                "id": acc.id,
                "username": acc.username,
                "email": acc.email,
                "phone": acc.phone,
                "proxy_used": acc.proxy_used,
                "ip_address": acc.ip_address,
                "verification_status": acc.verification_status,
                "status": acc.status.value,
                "created_at": acc.created_at.isoformat() if acc.created_at else None,
                "verified_at": acc.verified_at.isoformat() if acc.verified_at else None,
            }
            for acc in accounts
        ]
    }


@router.post("/account-generation/tasks/{task_id}/start")
async def start_generation_task(
    task_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Start account generation task (would trigger worker in production)
    """
    result = await db.execute(
        select(AccountGenerationTask).where(AccountGenerationTask.id == task_id)
    )
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != AccountGenStatusEnum.PENDING:
        raise HTTPException(
            status_code=400,
            detail=f"Task cannot be started from status: {task.status.value}"
        )

    # Update task status
    task.status = AccountGenStatusEnum.GENERATING
    task.started_at = datetime.now()
    await db.commit()

    # In production, this would enqueue the task to a worker
    # For now, we'll simulate by creating pending accounts

    # Audit log
    await audit_log(
        actor_user_id=1,
        operation="start_account_generation_task",
        payload={
            "task_id": task.id,
        },
        session=db,
        ip_address=request.client.host if request.client else None
    )

    return {
        "success": True,
        "task_id": task.id,
        "status": task.status.value,
        "message": "Task started. Accounts will be generated in the background."
    }


@router.post("/account-generation/tasks/{task_id}/cancel")
async def cancel_generation_task(
    task_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Cancel account generation task
    """
    result = await db.execute(
        select(AccountGenerationTask).where(AccountGenerationTask.id == task_id)
    )
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status in [AccountGenStatusEnum.COMPLETED, AccountGenStatusEnum.FAILED]:
        raise HTTPException(
            status_code=400,
            detail=f"Task cannot be cancelled from status: {task.status.value}"
        )

    # Update task status
    task.status = AccountGenStatusEnum.SUSPENDED
    await db.commit()

    # Audit log
    await audit_log(
        actor_user_id=1,
        operation="cancel_account_generation_task",
        payload={
            "task_id": task.id,
        },
        session=db,
        ip_address=request.client.host if request.client else None
    )

    return {
        "success": True,
        "task_id": task.id,
        "status": task.status.value,
        "message": "Task cancelled."
    }


@router.delete("/account-generation/tasks/{task_id}")
async def delete_generation_task(
    task_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete account generation task
    """
    result = await db.execute(
        select(AccountGenerationTask).where(AccountGenerationTask.id == task_id)
    )
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Delete associated generated accounts first
    accounts_result = await db.execute(
        select(GeneratedAccount).where(GeneratedAccount.task_id == task_id)
    )
    accounts = accounts_result.scalars().all()

    for account in accounts:
        await db.delete(account)

    await db.delete(task)
    await db.commit()

    # Audit log
    await audit_log(
        actor_user_id=1,
        operation="delete_account_generation_task",
        payload={
            "task_id": task.id,
            "deleted_accounts_count": len(accounts)
        },
        session=db,
        ip_address=request.client.host if request.client else None
    )

    return {
        "success": True,
        "message": f"Task {task_id} and {len(accounts)} accounts deleted"
    }


@router.get("/account-generation/accounts")
async def list_generated_accounts(
    platform: Optional[str] = None,
    task_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """
    List generated accounts
    """
    query = select(GeneratedAccount).order_by(GeneratedAccount.created_at.desc())

    if platform:
        try:
            platform_enum = PlatformEnum[platform.upper()]
            query = query.where(GeneratedAccount.platform == platform_enum)
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Invalid platform: {platform}")

    if task_id:
        query = query.where(GeneratedAccount.task_id == task_id)

    if status:
        try:
            status_enum = StatusEnum[status.upper()]
            query = query.where(GeneratedAccount.status == status_enum)
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    query = query.limit(limit)
    result = await db.execute(query)
    accounts = result.scalars().all()

    return {
        "accounts": [
            {
                "id": acc.id,
                "task_id": acc.task_id,
                "platform": acc.platform.value,
                "username": acc.username,
                "email": acc.email,
                "phone": acc.phone,
                "proxy_used": acc.proxy_used,
                "verification_status": acc.verification_status,
                "status": acc.status.value,
                "created_at": acc.created_at.isoformat() if acc.created_at else None,
                "verified_at": acc.verified_at.isoformat() if acc.verified_at else None,
                "last_login": acc.last_login.isoformat() if acc.last_login else None,
            }
            for acc in accounts
        ]
    }
