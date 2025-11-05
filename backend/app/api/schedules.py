from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

from ..models.database import get_db, Campaign, RunStatusEnum
from ..services.audit_service import audit_log


router = APIRouter()


class CreateCampaignRequest(BaseModel):
    name: str
    description: Optional[str] = None
    start_date: str
    end_date: str
    target_metrics: Dict[str, Any]
    run_ids: list[int] = []


class UpdateCampaignRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    target_metrics: Optional[Dict[str, Any]] = None
    run_ids: Optional[list[int]] = None
    status: Optional[str] = None


@router.post("/campaigns")
async def create_campaign(
    data: CreateCampaignRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a campaign
    """
    campaign = Campaign(
        name=data.name,
        description=data.description,
        start_date=datetime.fromisoformat(data.start_date),
        end_date=datetime.fromisoformat(data.end_date),
        target_metrics=data.target_metrics,
        run_ids=data.run_ids,
        created_by=1,  # TODO: Get from authenticated user
        status=RunStatusEnum.PENDING
    )

    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)

    # Audit log
    await audit_log(
        actor_user_id=1,
        operation="create_campaign",
        payload={
            "campaign_id": campaign.id,
            "name": data.name,
        },
        session=db,
        ip_address=request.client.host
    )

    return {
        "success": True,
        "campaign_id": campaign.id
    }


@router.get("/campaigns/{campaign_id}")
async def get_campaign(
    campaign_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get campaign details
    """
    result = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id)
    )
    campaign = result.scalar_one_or_none()

    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    return {
        "id": campaign.id,
        "name": campaign.name,
        "description": campaign.description,
        "start_date": campaign.start_date.isoformat(),
        "end_date": campaign.end_date.isoformat(),
        "target_metrics": campaign.target_metrics,
        "run_ids": campaign.run_ids,
        "status": campaign.status.value,
        "created_at": campaign.created_at.isoformat(),
        "updated_at": campaign.updated_at.isoformat() if campaign.updated_at else None,
    }


@router.get("/campaigns")
async def list_campaigns(
    status: Optional[str] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """
    List campaigns
    """
    query = select(Campaign)

    if status:
        query = query.where(Campaign.status == RunStatusEnum[status.upper()])

    query = query.order_by(Campaign.created_at.desc()).limit(limit)

    result = await db.execute(query)
    campaigns = result.scalars().all()

    return {
        "campaigns": [
            {
                "id": campaign.id,
                "name": campaign.name,
                "start_date": campaign.start_date.isoformat(),
                "end_date": campaign.end_date.isoformat(),
                "status": campaign.status.value,
                "run_count": len(campaign.run_ids),
                "created_at": campaign.created_at.isoformat(),
            }
            for campaign in campaigns
        ],
        "count": len(campaigns)
    }


@router.patch("/campaigns/{campaign_id}")
async def update_campaign(
    campaign_id: int,
    data: UpdateCampaignRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Update campaign
    """
    result = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id)
    )
    campaign = result.scalar_one_or_none()

    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Update fields
    if data.name:
        campaign.name = data.name

    if data.description:
        campaign.description = data.description

    if data.start_date:
        campaign.start_date = datetime.fromisoformat(data.start_date)

    if data.end_date:
        campaign.end_date = datetime.fromisoformat(data.end_date)

    if data.target_metrics:
        campaign.target_metrics = data.target_metrics

    if data.run_ids is not None:
        campaign.run_ids = data.run_ids

    if data.status:
        campaign.status = RunStatusEnum[data.status.upper()]

    await db.commit()

    # Audit log
    await audit_log(
        actor_user_id=1,
        operation="update_campaign",
        payload={
            "campaign_id": campaign_id,
            "changes": data.dict(exclude_none=True),
        },
        session=db,
        ip_address=request.client.host
    )

    return {
        "success": True,
        "campaign_id": campaign_id
    }


@router.delete("/campaigns/{campaign_id}")
async def delete_campaign(
    campaign_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete campaign (soft delete by setting status)
    """
    result = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id)
    )
    campaign = result.scalar_one_or_none()

    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    campaign.status = RunStatusEnum.ABORTED

    await db.commit()

    # Audit log
    await audit_log(
        actor_user_id=1,
        operation="delete_campaign",
        payload={
            "campaign_id": campaign_id,
        },
        session=db,
        ip_address=request.client.host
    )

    return {
        "success": True,
        "message": "Campaign deleted"
    }
