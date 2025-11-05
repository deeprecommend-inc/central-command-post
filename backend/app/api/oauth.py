from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, Any
import httpx

from ..models.database import get_db, Account, StatusEnum, PlatformEnum
from ..core.config import settings
from ..services.audit_service import audit_log


router = APIRouter()


class OAuthConfig:
    """OAuth configuration for each platform"""

    CONFIGS = {
        "youtube": {
            "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_url": "https://oauth2.googleapis.com/token",
            "scope": "https://www.googleapis.com/auth/youtube.force-ssl",
        },
        "x": {
            "auth_url": "https://twitter.com/i/oauth2/authorize",
            "token_url": "https://api.twitter.com/2/oauth2/token",
            "scope": "tweet.read tweet.write users.read follows.read follows.write",
        },
        "instagram": {
            "auth_url": "https://api.instagram.com/oauth/authorize",
            "token_url": "https://api.instagram.com/oauth/access_token",
            "scope": "instagram_basic instagram_content_publish",
        },
        "tiktok": {
            "auth_url": "https://www.tiktok.com/v2/auth/authorize",
            "token_url": "https://open.tiktokapis.com/v2/oauth/token",
            "scope": "video.upload video.publish",
        }
    }

    @classmethod
    def get_config(cls, platform: str) -> Dict[str, Any]:
        return cls.CONFIGS.get(platform.lower())


@router.get("/{platform}/connect")
async def oauth_connect(
    platform: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Initiate OAuth connection
    Returns authorization URL for user to visit
    """
    config = OAuthConfig.get_config(platform)
    if not config:
        raise HTTPException(status_code=400, detail=f"Unsupported platform: {platform}")

    # Get client credentials
    client_id = getattr(settings, f"{platform.upper()}_CLIENT_ID")
    if not client_id:
        raise HTTPException(
            status_code=500,
            detail=f"OAuth not configured for {platform}"
        )

    # Build authorization URL
    redirect_uri = f"{settings.OAUTH_REDIRECT_BASE}/oauth/{platform}/callback"

    auth_params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": config["scope"],
        "state": "random_state_string",  # Should be cryptographically random
    }

    auth_url = config["auth_url"]
    param_string = "&".join([f"{k}={v}" for k, v in auth_params.items()])
    full_auth_url = f"{auth_url}?{param_string}"

    return {
        "auth_url": full_auth_url,
        "platform": platform
    }


@router.get("/{platform}/callback")
async def oauth_callback(
    platform: str,
    code: str,
    state: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    OAuth callback endpoint
    Exchange code for access token and save account
    """
    config = OAuthConfig.get_config(platform)
    if not config:
        raise HTTPException(status_code=400, detail=f"Unsupported platform: {platform}")

    client_id = getattr(settings, f"{platform.upper()}_CLIENT_ID")
    client_secret = getattr(settings, f"{platform.upper()}_CLIENT_SECRET")

    if not client_id or not client_secret:
        raise HTTPException(
            status_code=500,
            detail=f"OAuth not configured for {platform}"
        )

    # Exchange code for token
    redirect_uri = f"{settings.OAUTH_REDIRECT_BASE}/oauth/{platform}/callback"

    token_data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "client_secret": client_secret,
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(config["token_url"], data=token_data)
            response.raise_for_status()
            token_response = response.json()

            access_token = token_response.get("access_token")
            refresh_token = token_response.get("refresh_token")

            if not access_token:
                raise HTTPException(
                    status_code=400,
                    detail="Failed to obtain access token"
                )

            # TODO: Encrypt tokens using KMS envelope encryption
            # For now, storing as-is (NOT PRODUCTION READY)
            encrypted_token_ref = access_token  # Should be encrypted

            # Create account record
            # Note: owner_user_id should come from authenticated session
            account = Account(
                platform=PlatformEnum[platform.upper()],
                oauth_token_ref=encrypted_token_ref,
                owner_user_id=1,  # TODO: Get from authenticated user
                status=StatusEnum.ACTIVE,
                account_metadata={
                    "refresh_token": refresh_token,
                    "scope": config["scope"],
                }
            )

            db.add(account)
            await db.commit()
            await db.refresh(account)

            # Audit log
            await audit_log(
                actor_user_id=1,
                operation="oauth_connect",
                payload={
                    "platform": platform,
                    "account_id": account.id,
                },
                session=db,
                ip_address=request.client.host
            )

            return {
                "success": True,
                "account_id": account.id,
                "platform": platform
            }

        except httpx.HTTPError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to exchange OAuth code: {str(e)}"
            )


@router.get("/{platform}/status")
async def oauth_status(
    platform: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get OAuth connection status for platform
    """
    # TODO: Get from authenticated user
    owner_user_id = 1

    result = await db.execute(
        select(Account).where(
            Account.platform == PlatformEnum[platform.upper()],
            Account.owner_user_id == owner_user_id,
            Account.status == StatusEnum.ACTIVE
        )
    )

    accounts = result.scalars().all()

    return {
        "platform": platform,
        "connected": len(accounts) > 0,
        "accounts": [
            {
                "id": acc.id,
                "display_name": acc.display_name,
                "status": acc.status.value,
                "created_at": acc.created_at.isoformat()
            }
            for acc in accounts
        ]
    }


@router.post("/{platform}/disconnect/{account_id}")
async def oauth_disconnect(
    platform: str,
    account_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Disconnect OAuth account
    """
    result = await db.execute(
        select(Account).where(Account.id == account_id)
    )

    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    # Set status to inactive
    account.status = StatusEnum.INACTIVE
    await db.commit()

    # Audit log
    await audit_log(
        actor_user_id=1,
        operation="oauth_disconnect",
        payload={
            "platform": platform,
            "account_id": account_id,
        },
        session=db,
        ip_address=request.client.host
    )

    return {
        "success": True,
        "message": "Account disconnected"
    }
