from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
from typing import Optional
import csv
import json
import io

from ..models.database import get_db, Run, RunEvent, ObservabilityMetric, AuditWORM, PlatformEnum

router = APIRouter()


@router.get("/exports")
async def export_data(
    type: str = "csv",  # csv or json
    data_type: str = "runs",  # runs, events, metrics, audits
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    platform: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Export data in CSV or JSON format
    """
    if type not in ["csv", "json"]:
        raise HTTPException(status_code=400, detail="Invalid type. Must be 'csv' or 'json'")

    if data_type not in ["runs", "events", "metrics", "audits"]:
        raise HTTPException(status_code=400, detail="Invalid data_type")

    # Parse dates
    start_dt = datetime.fromisoformat(start_date) if start_date else None
    end_dt = datetime.fromisoformat(end_date) if end_date else None

    if not start_dt or not end_dt:
        raise HTTPException(status_code=400, detail="start_date and end_date are required")

    # Fetch data based on type
    if data_type == "runs":
        data = await export_runs(db, start_dt, end_dt, platform)
    elif data_type == "events":
        data = await export_events(db, start_dt, end_dt, platform)
    elif data_type == "metrics":
        data = await export_metrics(db, start_dt, end_dt, platform)
    elif data_type == "audits":
        data = await export_audits(db, start_dt, end_dt)
    else:
        raise HTTPException(status_code=400, detail="Invalid data_type")

    # Format output
    if type == "csv":
        return export_as_csv(data, data_type)
    else:
        return export_as_json(data, data_type)


async def export_runs(
    db: AsyncSession,
    start_date: datetime,
    end_date: datetime,
    platform: Optional[str]
):
    """Export runs data"""
    query = select(Run).where(
        Run.created_at >= start_date,
        Run.created_at <= end_date
    )

    if platform and platform != "all":
        query = query.where(Run.platform == PlatformEnum[platform.upper()])

    result = await db.execute(query)
    runs = result.scalars().all()

    return [
        {
            "id": run.id,
            "platform": run.platform.value,
            "engine": run.engine.value,
            "status": run.status.value,
            "schedule_json": json.dumps(run.schedule_json) if run.schedule_json else "",
            "rate_config": json.dumps(run.rate_config) if run.rate_config else "",
            "observability_json": json.dumps(run.observability_json) if run.observability_json else "",
            "prompt_json": json.dumps(run.prompt_json) if run.prompt_json else "",
            "approval_required": run.approval_required,
            "created_at": run.created_at.isoformat(),
            "updated_at": run.updated_at.isoformat() if run.updated_at else "",
        }
        for run in runs
    ]


async def export_events(
    db: AsyncSession,
    start_date: datetime,
    end_date: datetime,
    platform: Optional[str]
):
    """Export run events data"""
    query = select(RunEvent).where(
        RunEvent.started_at >= start_date,
        RunEvent.started_at <= end_date
    )

    result = await db.execute(query)
    events = result.scalars().all()

    # Filter by platform if specified
    if platform and platform != "all":
        # Get run IDs for the platform
        run_query = select(Run.id).where(Run.platform == PlatformEnum[platform.upper()])
        run_result = await db.execute(run_query)
        run_ids = [r[0] for r in run_result.fetchall()]
        events = [e for e in events if e.run_id in run_ids]

    return [
        {
            "id": event.id,
            "run_id": event.run_id,
            "action": event.action,
            "started_at": event.started_at.isoformat(),
            "ended_at": event.ended_at.isoformat() if event.ended_at else "",
            "response_code": event.response_code,
            "detail": json.dumps(event.detail) if event.detail else "",
            "success": event.success,
        }
        for event in events
    ]


async def export_metrics(
    db: AsyncSession,
    start_date: datetime,
    end_date: datetime,
    platform: Optional[str]
):
    """Export observability metrics data"""
    query = select(ObservabilityMetric).where(
        ObservabilityMetric.timestamp >= start_date,
        ObservabilityMetric.timestamp <= end_date
    )

    result = await db.execute(query)
    metrics = result.scalars().all()

    # Filter by platform if specified
    if platform and platform != "all":
        # Get run IDs for the platform
        run_query = select(Run.id).where(Run.platform == PlatformEnum[platform.upper()])
        run_result = await db.execute(run_query)
        run_ids = [r[0] for r in run_result.fetchall()]
        metrics = [m for m in metrics if m.run_id in run_ids]

    return [
        {
            "id": metric.id,
            "run_id": metric.run_id,
            "category": metric.category,
            "metric_key": metric.metric_key,
            "metric_value": metric.metric_value,
            "threshold_value": metric.threshold_value,
            "violated": metric.violated,
            "action_taken": metric.action_taken,
            "timestamp": metric.timestamp.isoformat(),
        }
        for metric in metrics
    ]


async def export_audits(
    db: AsyncSession,
    start_date: datetime,
    end_date: datetime
):
    """Export audit logs"""
    query = select(AuditWORM).where(
        AuditWORM.timestamp >= start_date,
        AuditWORM.timestamp <= end_date
    )

    result = await db.execute(query)
    audits = result.scalars().all()

    return [
        {
            "id": audit.id,
            "timestamp": audit.timestamp.isoformat(),
            "actor_user_id": audit.actor_user_id,
            "operation": audit.operation,
            "payload_immutable": json.dumps(audit.payload_immutable) if audit.payload_immutable else "",
            "ip_address": audit.ip_address or "",
            "hash": audit.hash,
        }
        for audit in audits
    ]


def export_as_csv(data: list, data_type: str):
    """Export data as CSV"""
    if not data:
        raise HTTPException(status_code=404, detail="No data found for the specified criteria")

    # Create CSV in memory
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=data[0].keys())
    writer.writeheader()
    writer.writerows(data)

    # Return as streaming response
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=export_{data_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        }
    )


def export_as_json(data: list, data_type: str):
    """Export data as JSON"""
    if not data:
        raise HTTPException(status_code=404, detail="No data found for the specified criteria")

    # Return as JSON response
    json_data = json.dumps(data, indent=2, ensure_ascii=False)

    return Response(
        content=json_data,
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename=export_{data_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        }
    )
