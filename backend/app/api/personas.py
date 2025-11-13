from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from ..models.database import (
    get_db,
    Persona,
    PersonaTypeEnum,
    GeneratedAccount,
    PlatformEnum
)

router = APIRouter(prefix="/personas")


# Pydantic Models
class PersonaCreate(BaseModel):
    name: str
    persona_type: PersonaTypeEnum
    age_range: Optional[str] = None
    gender: Optional[str] = None
    location_country: Optional[str] = None
    location_city: Optional[str] = None
    timezone: Optional[str] = "Asia/Tokyo"
    language: Optional[str] = "ja-JP"
    interests: Optional[List[str]] = []
    occupation: Optional[str] = None
    education_level: Optional[str] = None
    activity_hours: Optional[dict] = {}
    posting_frequency: Optional[str] = "medium"
    interaction_style: Optional[str] = "friendly"
    browser_fingerprint_config: Optional[dict] = {}
    preferred_device: Optional[str] = "desktop"
    screen_resolution: Optional[str] = "1920x1080"
    profile_template: Optional[dict] = {}
    avatar_style: Optional[str] = None
    bio_template: Optional[str] = None


class PersonaUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None
    age_range: Optional[str] = None
    gender: Optional[str] = None
    location_country: Optional[str] = None
    location_city: Optional[str] = None
    timezone: Optional[str] = None
    language: Optional[str] = None
    interests: Optional[List[str]] = None
    occupation: Optional[str] = None
    education_level: Optional[str] = None
    activity_hours: Optional[dict] = None
    posting_frequency: Optional[str] = None
    interaction_style: Optional[str] = None
    browser_fingerprint_config: Optional[dict] = None
    preferred_device: Optional[str] = None
    screen_resolution: Optional[str] = None
    profile_template: Optional[dict] = None
    avatar_style: Optional[str] = None
    bio_template: Optional[str] = None


class PersonaResponse(BaseModel):
    id: int
    name: str
    persona_type: str
    age_range: Optional[str]
    gender: Optional[str]
    location_country: Optional[str]
    location_city: Optional[str]
    timezone: Optional[str]
    language: Optional[str]
    interests: List[str]
    occupation: Optional[str]
    education_level: Optional[str]
    activity_hours: dict
    posting_frequency: Optional[str]
    interaction_style: Optional[str]
    browser_fingerprint_config: dict
    preferred_device: Optional[str]
    screen_resolution: Optional[str]
    profile_template: dict
    avatar_style: Optional[str]
    bio_template: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]

    # Associated accounts count
    accounts_count: int = 0

    class Config:
        from_attributes = True


# API Endpoints
@router.post("/", response_model=PersonaResponse)
async def create_persona(
    persona_data: PersonaCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new persona (人格)"""

    persona = Persona(
        name=persona_data.name,
        persona_type=persona_data.persona_type,
        age_range=persona_data.age_range,
        gender=persona_data.gender,
        location_country=persona_data.location_country,
        location_city=persona_data.location_city,
        timezone=persona_data.timezone,
        language=persona_data.language,
        interests=persona_data.interests or [],
        occupation=persona_data.occupation,
        education_level=persona_data.education_level,
        activity_hours=persona_data.activity_hours or {},
        posting_frequency=persona_data.posting_frequency,
        interaction_style=persona_data.interaction_style,
        browser_fingerprint_config=persona_data.browser_fingerprint_config or {},
        preferred_device=persona_data.preferred_device,
        screen_resolution=persona_data.screen_resolution,
        profile_template=persona_data.profile_template or {},
        avatar_style=persona_data.avatar_style,
        bio_template=persona_data.bio_template,
        created_by=1  # TODO: Get from authenticated user
    )

    db.add(persona)
    await db.commit()
    await db.refresh(persona)

    # Get accounts count
    accounts_result = await db.execute(
        select(func.count(GeneratedAccount.id)).where(GeneratedAccount.persona_id == persona.id)
    )
    accounts_count = accounts_result.scalar() or 0

    response = PersonaResponse(
        **{k: v for k, v in persona.__dict__.items() if not k.startswith('_')},
        accounts_count=accounts_count
    )

    return response


@router.get("/", response_model=List[PersonaResponse])
async def list_personas(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    persona_type: Optional[PersonaTypeEnum] = None,
    is_active: Optional[bool] = None,
    db: AsyncSession = Depends(get_db)
):
    """List all personas"""

    query = select(Persona)

    # Filters
    if persona_type:
        query = query.where(Persona.persona_type == persona_type)
    if is_active is not None:
        query = query.where(Persona.is_active == is_active)

    query = query.order_by(Persona.created_at.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
    personas = result.scalars().all()

    # Get accounts count for each persona
    response_list = []
    for persona in personas:
        accounts_result = await db.execute(
            select(func.count(GeneratedAccount.id)).where(GeneratedAccount.persona_id == persona.id)
        )
        accounts_count = accounts_result.scalar() or 0

        response_list.append(PersonaResponse(
            **{k: v for k, v in persona.__dict__.items() if not k.startswith('_')},
            accounts_count=accounts_count
        ))

    return response_list


@router.get("/{persona_id}", response_model=PersonaResponse)
async def get_persona(
    persona_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get specific persona with detailed information"""

    result = await db.execute(
        select(Persona).where(Persona.id == persona_id)
    )
    persona = result.scalar_one_or_none()

    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")

    # Get accounts count
    accounts_result = await db.execute(
        select(func.count(GeneratedAccount.id)).where(GeneratedAccount.persona_id == persona_id)
    )
    accounts_count = accounts_result.scalar() or 0

    return PersonaResponse(
        **{k: v for k, v in persona.__dict__.items() if not k.startswith('_')},
        accounts_count=accounts_count
    )


@router.get("/{persona_id}/accounts")
async def get_persona_accounts(
    persona_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get all accounts associated with this persona"""

    # Verify persona exists
    result = await db.execute(
        select(Persona).where(Persona.id == persona_id)
    )
    persona = result.scalar_one_or_none()

    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")

    # Get all accounts
    accounts_result = await db.execute(
        select(GeneratedAccount).where(GeneratedAccount.persona_id == persona_id)
    )
    accounts = accounts_result.scalars().all()

    return {
        "persona_id": persona_id,
        "persona_name": persona.name,
        "accounts": [
            {
                "id": acc.id,
                "platform": acc.platform.value,
                "username": acc.username,
                "email": acc.email,
                "status": acc.status.value,
                "mulogin_profile_id": acc.mulogin_profile_id,
                "proxy_used": acc.proxy_used,
                "ip_address": acc.ip_address,
                "verification_status": acc.verification_status,
                "created_at": acc.created_at.isoformat() if acc.created_at else None,
            }
            for acc in accounts
        ]
    }


@router.patch("/{persona_id}", response_model=PersonaResponse)
async def update_persona(
    persona_id: int,
    update_data: PersonaUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update persona information"""

    result = await db.execute(
        select(Persona).where(Persona.id == persona_id)
    )
    persona = result.scalar_one_or_none()

    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")

    # Update fields
    update_dict = update_data.dict(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(persona, key, value)

    await db.commit()
    await db.refresh(persona)

    # Get accounts count
    accounts_result = await db.execute(
        select(func.count(GeneratedAccount.id)).where(GeneratedAccount.persona_id == persona_id)
    )
    accounts_count = accounts_result.scalar() or 0

    return PersonaResponse(
        **{k: v for k, v in persona.__dict__.items() if not k.startswith('_')},
        accounts_count=accounts_count
    )


@router.delete("/{persona_id}")
async def delete_persona(
    persona_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete a persona (does not delete associated accounts)"""

    result = await db.execute(
        select(Persona).where(Persona.id == persona_id)
    )
    persona = result.scalar_one_or_none()

    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")

    # Check if persona has associated accounts
    accounts_result = await db.execute(
        select(func.count(GeneratedAccount.id)).where(GeneratedAccount.persona_id == persona_id)
    )
    accounts_count = accounts_result.scalar() or 0

    if accounts_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete persona with {accounts_count} associated accounts. Remove accounts first."
        )

    await db.delete(persona)
    await db.commit()

    return {
        "success": True,
        "message": f"Persona {persona_id} deleted successfully"
    }


@router.get("/stats/overview")
async def get_personas_stats(db: AsyncSession = Depends(get_db)):
    """Get statistics about personas"""

    # Total personas
    total_result = await db.execute(select(func.count(Persona.id)))
    total = total_result.scalar()

    # Active personas
    active_result = await db.execute(
        select(func.count(Persona.id)).where(Persona.is_active == True)
    )
    active = active_result.scalar()

    # By type
    type_stats = {}
    for persona_type in PersonaTypeEnum:
        result = await db.execute(
            select(func.count(Persona.id)).where(Persona.persona_type == persona_type)
        )
        type_stats[persona_type.value] = result.scalar()

    # Total accounts linked to personas
    accounts_result = await db.execute(
        select(func.count(GeneratedAccount.id)).where(GeneratedAccount.persona_id != None)
    )
    total_accounts = accounts_result.scalar()

    return {
        "total_personas": total,
        "active_personas": active,
        "inactive_personas": total - active,
        "by_type": type_stats,
        "total_linked_accounts": total_accounts
    }
