from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from enum import Enum


class ActionType(str, Enum):
    POST = "post"
    REPLY = "reply"
    LIKE = "like"
    FOLLOW = "follow"
    REPOST = "repost"
    COMMENT = "comment"


class AdapterResponse:
    """Standardized adapter response"""

    def __init__(
        self,
        success: bool,
        response_code: int,
        data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        rate_limit_remaining: Optional[int] = None,
        rate_limit_reset: Optional[int] = None,
    ):
        self.success = success
        self.response_code = response_code
        self.data = data or {}
        self.error = error
        self.rate_limit_remaining = rate_limit_remaining
        self.rate_limit_reset = rate_limit_reset

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "response_code": self.response_code,
            "data": self.data,
            "error": self.error,
            "rate_limit_remaining": self.rate_limit_remaining,
            "rate_limit_reset": self.rate_limit_reset,
        }


class BaseSNSAdapter(ABC):
    """Base adapter for SNS platforms"""

    def __init__(self, access_token: str, config: Optional[Dict[str, Any]] = None):
        self.access_token = access_token
        self.config = config or {}

    @abstractmethod
    async def post(self, content: str, **kwargs) -> AdapterResponse:
        """Create a new post"""
        pass

    @abstractmethod
    async def reply(self, post_id: str, content: str, **kwargs) -> AdapterResponse:
        """Reply to a post"""
        pass

    @abstractmethod
    async def like(self, post_id: str) -> AdapterResponse:
        """Like a post"""
        pass

    @abstractmethod
    async def follow(self, user_id: str) -> AdapterResponse:
        """Follow a user"""
        pass

    @abstractmethod
    async def get_mentions(self, limit: int = 20) -> AdapterResponse:
        """Get mentions"""
        pass

    @abstractmethod
    async def get_analytics(self, post_id: Optional[str] = None) -> AdapterResponse:
        """Get analytics/metrics"""
        pass

    @abstractmethod
    async def verify_token(self) -> bool:
        """Verify access token is valid"""
        pass

    def get_rate_limits(self) -> Dict[str, int]:
        """
        Get platform-specific rate limits
        Returns: {action: requests_per_hour}
        """
        return {
            "post": 100,
            "reply": 200,
            "like": 500,
            "follow": 100,
        }
