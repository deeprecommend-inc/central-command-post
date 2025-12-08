"""
Prompt-based browser action API (No OAuth required)
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

from ..models.database import (
    get_db,
    Account,
    GeneratedAccount,
    PlatformEnum,
)
from ..services.browser_agent import browser_agent
from ..services.audit_service import audit_log

router = APIRouter()


class BrowserActionRequest(BaseModel):
    """Request model for prompt-based browser actions"""
    task: str = Field(..., description="Natural language task description")
    platform: str = Field(..., description="Platform: youtube, x, instagram, tiktok")
    account_id: Optional[int] = Field(None, description="Account ID to use (from accounts or generated_accounts table)")
    use_generated_account: bool = Field(False, description="Use generated_account instead of account")
    browser_config: Optional[dict] = Field(default_factory=dict, description="Browser configuration (headless, proxy, etc)")
    use_cloud: bool = Field(False, description="Use Browser Use Cloud for stealth")


class BrowserActionResponse(BaseModel):
    """Response model for browser actions"""
    success: bool
    result: Optional[str]
    actions_taken: List[str]
    execution_log: List[str]
    screenshots: List[str]
    execution_time: float
    error: Optional[str]


@router.post("/browser-actions/execute", response_model=BrowserActionResponse)
async def execute_browser_action(
    request: BrowserActionRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Execute a natural language task using browser automation

    No OAuth required - uses browser automation with credentials

    Examples:

    1. Post a video:
    {
        "task": "Post a video with title 'My Test Video' and description 'This is a test'",
        "platform": "youtube",
        "account_id": 1,
        "browser_config": {"headless": true}
    }

    2. Like top videos:
    {
        "task": "Like the top 5 videos in my feed",
        "platform": "youtube",
        "account_id": 1
    }

    3. Follow users:
    {
        "task": "Follow @user1, @user2, and @user3",
        "platform": "x",
        "account_id": 1
    }

    4. Comment on content:
    {
        "task": "Comment 'Great content!' on the latest post from @techcreator",
        "platform": "instagram",
        "account_id": 1
    }
    """

    # Validate platform
    try:
        platform_enum = PlatformEnum[request.platform.upper()]
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Invalid platform: {request.platform}")

    # Get account credentials
    account_credentials = None

    if request.account_id:
        if request.use_generated_account:
            # Use GeneratedAccount
            result = await db.execute(
                select(GeneratedAccount).where(GeneratedAccount.id == request.account_id)
            )
            account = result.scalar_one_or_none()

            if not account:
                raise HTTPException(status_code=404, detail="Generated account not found")

            if account.platform != platform_enum:
                raise HTTPException(
                    status_code=400,
                    detail=f"Account platform ({account.platform.value}) does not match request platform ({request.platform})"
                )

            account_credentials = {
                "username": account.username,
                "email": account.email,
                "password": account.password_encrypted,  # TODO: Decrypt
            }
        else:
            # Use Account (legacy)
            result = await db.execute(
                select(Account).where(Account.id == request.account_id)
            )
            account = result.scalar_one_or_none()

            if not account:
                raise HTTPException(status_code=404, detail="Account not found")

            if account.platform != platform_enum:
                raise HTTPException(
                    status_code=400,
                    detail=f"Account platform ({account.platform.value}) does not match request platform ({request.platform})"
                )

            account_credentials = {
                "username": account.username,
                "email": account.email,
                "password": account.password_encrypted,  # TODO: Decrypt
            }

    # Execute browser action
    result = await browser_agent.execute_task(
        task=request.task,
        platform=request.platform,
        account_credentials=account_credentials,
        browser_config=request.browser_config,
        use_cloud=request.use_cloud,
    )

    # Audit log
    await audit_log(
        actor_user_id=0,  # TODO: Get from auth
        operation="browser_action_execute",
        payload={
            "task": request.task,
            "platform": request.platform,
            "account_id": request.account_id,
            "success": result["success"],
            "actions_taken": result.get("actions_taken", []),
            "execution_log": result.get("execution_log", []),
            "error": result.get("error"),
        },
        session=db,
    )

    return BrowserActionResponse(**result)


@router.post("/browser-actions/login")
async def login_to_platform(
    platform: str,
    account_id: int,
    use_generated_account: bool = False,
    headless: bool = True,
    db: AsyncSession = Depends(get_db)
):
    """
    Login to a platform and save session/cookies

    Useful for establishing a session before performing actions
    """

    # Validate platform
    try:
        platform_enum = PlatformEnum[platform.upper()]
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Invalid platform: {platform}")

    # Get account
    if use_generated_account:
        result = await db.execute(
            select(GeneratedAccount).where(GeneratedAccount.id == account_id)
        )
        account = result.scalar_one_or_none()
    else:
        result = await db.execute(
            select(Account).where(Account.id == account_id)
        )
        account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    # Login
    login_result = await browser_agent.login_to_platform(
        platform=platform,
        username=account.username,
        email=account.email or "",
        password=account.password_encrypted,  # TODO: Decrypt
        headless=headless,
    )

    # Audit log
    await audit_log(
        actor_user_id=0,
        operation="browser_action_login",
        payload={
            "platform": platform,
            "account_id": account_id,
            "success": login_result["success"],
        },
        session=db,
    )

    return login_result


@router.get("/browser-actions/examples")
async def get_task_examples():
    """
    Get example tasks for different platforms
    """

    return {
        "youtube": [
            "Post a video with title 'My Tutorial' and description 'Learn programming'",
            "Like the top 10 videos in my feed",
            "Subscribe to channels that posted videos about AI",
            "Comment 'Great video!' on the latest video from @techchannel",
            "Search for 'python tutorial' and like the top 3 results",
        ],
        "x": [
            "Post a tweet: 'Hello World from browser automation!'",
            "Like the latest 5 tweets in my timeline",
            "Follow @user1, @user2, and @user3",
            "Retweet the latest post from @technews",
            "Reply 'Interesting!' to the top tweet about AI",
        ],
        "instagram": [
            "Post a photo with caption 'Beautiful sunset'",
            "Like the latest 10 posts in my feed",
            "Follow users who liked my latest post",
            "Comment 'Amazing!' on @user's latest post",
            "Search for #travel and like the top 5 posts",
        ],
        "tiktok": [
            "Post a video with title 'Dance Challenge'",
            "Like the top 10 videos in For You page",
            "Follow creators who posted videos about cooking",
            "Comment 'LOL!' on the latest video from @creator",
            "Search for 'funny cats' and like the top 3 videos",
        ],
    }
