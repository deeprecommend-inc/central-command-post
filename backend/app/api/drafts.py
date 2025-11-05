from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

from ..models.database import get_db, AIDraft, Run
from ..services.ai_service import AIService, SafetyFilter, DuplicationChecker
from ..services.audit_service import audit_log


router = APIRouter()


class GenerateRequest(BaseModel):
    task: str  # "reply", "post", "hashtags"
    platform: str
    context: Dict[str, Any]
    custom_prompt: Optional[str] = None
    ng_words: List[str] = []
    previous_contents: List[str] = []


class ApproveRequest(BaseModel):
    approved_outputs: Dict[str, Any]


@router.post("/generate")
async def generate_drafts(
    data: GenerateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Generate AI drafts
    """
    # Initialize AI service
    ai_service = AIService(provider="anthropic")

    # Setup filters
    safety_filter = SafetyFilter(ng_words=data.ng_words)
    duplication_checker = DuplicationChecker(previous_contents=data.previous_contents)

    # Generate
    result = await ai_service.generate(
        task=data.task,
        context=data.context,
        custom_prompt=data.custom_prompt,
        safety_filter=safety_filter,
        duplication_checker=duplication_checker
    )

    if not result["success"]:
        raise HTTPException(
            status_code=500,
            detail=f"AI generation failed: {result.get('error')}"
        )

    # Create draft record (without run_id for standalone generation)
    draft = AIDraft(
        run_id=data.context.get("run_id", 0),  # 0 if standalone
        outputs_json=result["data"],
        toxicity_score=result["toxicity_score"],
        duplication_rate=result["duplication_rate"],
        approved=False
    )

    db.add(draft)
    await db.commit()
    await db.refresh(draft)

    # Audit log
    await audit_log(
        actor_user_id=1,
        operation="generate_drafts",
        payload={
            "draft_id": draft.id,
            "task": data.task,
            "platform": data.platform,
        },
        session=db,
        ip_address=request.client.host
    )

    return {
        "success": True,
        "draft_id": draft.id,
        "outputs": result["data"],
        "toxicity_score": result["toxicity_score"],
        "duplication_rate": result["duplication_rate"],
        "violations": result["violations"],
        "requires_approval": result["requires_approval"]
    }


@router.get("/{draft_id}")
async def get_draft(
    draft_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get draft details
    """
    result = await db.execute(
        select(AIDraft).where(AIDraft.id == draft_id)
    )
    draft = result.scalar_one_or_none()

    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    return {
        "id": draft.id,
        "run_id": draft.run_id,
        "outputs": draft.outputs_json,
        "toxicity_score": draft.toxicity_score,
        "duplication_rate": draft.duplication_rate,
        "approved": draft.approved,
        "approved_by": draft.approved_by,
        "approved_at": draft.approved_at.isoformat() if draft.approved_at else None,
        "created_at": draft.created_at.isoformat(),
    }


@router.get("/")
async def list_drafts(
    run_id: Optional[int] = None,
    approved: Optional[bool] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """
    List drafts with filters
    """
    query = select(AIDraft)

    if run_id is not None:
        query = query.where(AIDraft.run_id == run_id)

    if approved is not None:
        query = query.where(AIDraft.approved == approved)

    query = query.order_by(AIDraft.created_at.desc()).limit(limit)

    result = await db.execute(query)
    drafts = result.scalars().all()

    return {
        "drafts": [
            {
                "id": draft.id,
                "run_id": draft.run_id,
                "approved": draft.approved,
                "toxicity_score": draft.toxicity_score,
                "duplication_rate": draft.duplication_rate,
                "created_at": draft.created_at.isoformat(),
            }
            for draft in drafts
        ],
        "count": len(drafts)
    }


@router.post("/{draft_id}/approve")
async def approve_draft(
    draft_id: int,
    data: ApproveRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Approve a draft (with optional edits)
    """
    result = await db.execute(
        select(AIDraft).where(AIDraft.id == draft_id)
    )
    draft = result.scalar_one_or_none()

    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    # Update draft
    draft.approved = True
    draft.approved_by = 1  # TODO: Get from authenticated user
    draft.approved_at = datetime.utcnow()

    # Update outputs if edited
    if data.approved_outputs:
        draft.outputs_json = data.approved_outputs

    await db.commit()

    # Audit log
    await audit_log(
        actor_user_id=1,
        operation="approve_draft",
        payload={
            "draft_id": draft_id,
            "edited": bool(data.approved_outputs),
        },
        session=db,
        ip_address=request.client.host
    )

    return {
        "success": True,
        "draft_id": draft_id,
        "message": "Draft approved"
    }


@router.post("/{draft_id}/reject")
async def reject_draft(
    draft_id: int,
    reason: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Reject a draft
    """
    result = await db.execute(
        select(AIDraft).where(AIDraft.id == draft_id)
    )
    draft = result.scalar_one_or_none()

    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    # Mark as rejected (keep record for audit)
    draft.approved = False

    await db.commit()

    # Audit log
    await audit_log(
        actor_user_id=1,
        operation="reject_draft",
        payload={
            "draft_id": draft_id,
            "reason": reason,
        },
        session=db,
        ip_address=request.client.host
    )

    return {
        "success": True,
        "draft_id": draft_id,
        "message": "Draft rejected"
    }
