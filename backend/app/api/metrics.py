from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
from datetime import datetime, timedelta

from ..models.database import get_db, KPISnapshot, RunEvent, ObservabilityMetric, PlatformEnum


router = APIRouter()


@router.get("/kpi")
async def get_kpi_metrics(
    platform: Optional[str] = None,
    account_id: Optional[int] = None,
    days: int = 7,
    db: AsyncSession = Depends(get_db)
):
    """
    Get KPI metrics
    """
    start_date = datetime.utcnow() - timedelta(days=days)

    query = select(KPISnapshot).where(
        KPISnapshot.range_start >= start_date
    )

    if platform:
        query = query.where(KPISnapshot.platform == PlatformEnum[platform.upper()])

    if account_id:
        query = query.where(KPISnapshot.account_id == account_id)

    query = query.order_by(KPISnapshot.created_at.desc())

    result = await db.execute(query)
    snapshots = result.scalars().all()

    return {
        "snapshots": [
            {
                "id": snap.id,
                "platform": snap.platform.value,
                "account_id": snap.account_id,
                "range_start": snap.range_start.isoformat(),
                "range_end": snap.range_end.isoformat(),
                "metrics": snap.metrics_json,
                "created_at": snap.created_at.isoformat(),
            }
            for snap in snapshots
        ],
        "count": len(snapshots)
    }


@router.get("/execution-stats")
async def get_execution_stats(
    run_id: Optional[int] = None,
    platform: Optional[str] = None,
    days: int = 7,
    db: AsyncSession = Depends(get_db)
):
    """
    Get execution statistics
    """
    start_date = datetime.utcnow() - timedelta(days=days)

    query = select(
        RunEvent.action,
        func.count(RunEvent.id).label("total"),
        func.sum(func.cast(RunEvent.success, Integer)).label("successes"),
        func.avg(
            func.extract('epoch', RunEvent.ended_at - RunEvent.started_at)
        ).label("avg_duration_seconds")
    ).where(
        RunEvent.started_at >= start_date
    )

    if run_id:
        query = query.where(RunEvent.run_id == run_id)

    query = query.group_by(RunEvent.action)

    result = await db.execute(query)
    stats = result.all()

    return {
        "stats": [
            {
                "action": stat.action,
                "total": stat.total,
                "successes": stat.successes or 0,
                "failures": stat.total - (stat.successes or 0),
                "success_rate": (stat.successes or 0) / stat.total if stat.total > 0 else 0,
                "avg_duration_seconds": float(stat.avg_duration_seconds or 0),
            }
            for stat in stats
        ]
    }


@router.get("/observability")
async def get_observability_metrics(
    run_id: Optional[int] = None,
    category: Optional[str] = None,
    violated_only: bool = False,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """
    Get observability metrics
    """
    query = select(ObservabilityMetric)

    if run_id:
        query = query.where(ObservabilityMetric.run_id == run_id)

    if category:
        query = query.where(ObservabilityMetric.category == category)

    if violated_only:
        query = query.where(ObservabilityMetric.violated == True)

    query = query.order_by(ObservabilityMetric.timestamp.desc()).limit(limit)

    result = await db.execute(query)
    metrics = result.scalars().all()

    return {
        "metrics": [
            {
                "id": metric.id,
                "run_id": metric.run_id,
                "category": metric.category,
                "metric_key": metric.metric_key,
                "value": metric.metric_value,
                "threshold": metric.threshold_value,
                "violated": metric.violated,
                "action_taken": metric.action_taken,
                "timestamp": metric.timestamp.isoformat(),
            }
            for metric in metrics
        ],
        "count": len(metrics)
    }


@router.get("/dashboard")
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_db)
):
    """
    Get dashboard summary with key metrics
    """
    from sqlalchemy import Integer

    # Get counts for today
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    # Total runs today
    runs_today_result = await db.execute(
        select(func.count(Run.id)).where(Run.created_at >= today_start)
    )
    runs_today = runs_today_result.scalar() or 0

    # Events today
    events_today_result = await db.execute(
        select(
            func.count(RunEvent.id).label("total"),
            func.sum(func.cast(RunEvent.success, Integer)).label("successes")
        ).where(RunEvent.started_at >= today_start)
    )
    events_stats = events_today_result.first()

    # Pending approvals
    pending_approvals_result = await db.execute(
        select(func.count(AIDraft.id)).where(
            AIDraft.approved == False,
            AIDraft.created_at >= today_start
        )
    )
    pending_approvals = pending_approvals_result.scalar() or 0

    # Violations today
    violations_today_result = await db.execute(
        select(func.count(ObservabilityMetric.id)).where(
            ObservabilityMetric.violated == True,
            ObservabilityMetric.timestamp >= today_start
        )
    )
    violations_today = violations_today_result.scalar() or 0

    return {
        "today": {
            "runs": runs_today,
            "events_total": events_stats.total or 0,
            "events_success": events_stats.successes or 0,
            "events_failed": (events_stats.total or 0) - (events_stats.successes or 0),
            "pending_approvals": pending_approvals,
            "violations": violations_today,
        },
        "timestamp": datetime.utcnow().isoformat()
    }
