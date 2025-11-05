from typing import Dict, Any, Optional
import httpx

from .base_adapter import BaseSNSAdapter, AdapterResponse


class InstagramAdapter(BaseSNSAdapter):
    """Instagram Graph API Adapter"""

    def __init__(self, access_token: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(access_token, config)
        self.base_url = "https://graph.facebook.com/v18.0"
        self.instagram_account_id = config.get("instagram_account_id") if config else None

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None
    ) -> AdapterResponse:
        """Make API request"""
        url = f"{self.base_url}/{endpoint}"

        if params is None:
            params = {}
        params["access_token"] = self.access_token

        async with httpx.AsyncClient() as client:
            try:
                if method == "GET":
                    response = await client.get(url, params=params)
                elif method == "POST":
                    response = await client.post(url, params=params, json=data)
                elif method == "DELETE":
                    response = await client.delete(url, params=params)

                response.raise_for_status()

                return AdapterResponse(
                    success=True,
                    response_code=response.status_code,
                    data=response.json()
                )

            except httpx.HTTPStatusError as e:
                return AdapterResponse(
                    success=False,
                    response_code=e.response.status_code,
                    error=str(e)
                )

    async def post(self, content: str, **kwargs) -> AdapterResponse:
        """
        Create a media post (feed or reel)
        kwargs: image_url, video_url, media_type (IMAGE, VIDEO, REELS), location_id
        """
        if not self.instagram_account_id:
            return AdapterResponse(
                success=False,
                response_code=400,
                error="Instagram account ID not configured"
            )

        try:
            # Step 1: Create media container
            media_type = kwargs.get("media_type", "IMAGE")
            container_params = {
                "caption": content,
            }

            if media_type == "IMAGE":
                container_params["image_url"] = kwargs.get("image_url")
            elif media_type in ["VIDEO", "REELS"]:
                container_params["video_url"] = kwargs.get("video_url")
                container_params["media_type"] = media_type

            if kwargs.get("location_id"):
                container_params["location_id"] = kwargs.get("location_id")

            # Create container
            container_response = await self._make_request(
                "POST",
                f"{self.instagram_account_id}/media",
                data=container_params
            )

            if not container_response.success:
                return container_response

            creation_id = container_response.data.get("id")

            # Step 2: Publish media
            publish_response = await self._make_request(
                "POST",
                f"{self.instagram_account_id}/media_publish",
                data={"creation_id": creation_id}
            )

            return publish_response

        except Exception as e:
            return AdapterResponse(
                success=False,
                response_code=500,
                error=str(e)
            )

    async def reply(self, post_id: str, content: str, **kwargs) -> AdapterResponse:
        """Reply to a comment"""
        try:
            response = await self._make_request(
                "POST",
                f"{post_id}/replies",
                data={"message": content}
            )

            return response

        except Exception as e:
            return AdapterResponse(
                success=False,
                response_code=500,
                error=str(e)
            )

    async def like(self, post_id: str) -> AdapterResponse:
        """Like a media (not supported in Graph API for business accounts)"""
        return AdapterResponse(
            success=False,
            response_code=501,
            error="Like functionality not available in Instagram Graph API"
        )

    async def follow(self, user_id: str) -> AdapterResponse:
        """Follow a user (not supported in Graph API)"""
        return AdapterResponse(
            success=False,
            response_code=501,
            error="Follow functionality not available in Instagram Graph API"
        )

    async def get_mentions(self, limit: int = 20) -> AdapterResponse:
        """Get comments and mentions"""
        if not self.instagram_account_id:
            return AdapterResponse(
                success=False,
                response_code=400,
                error="Instagram account ID not configured"
            )

        try:
            # Get recent media
            media_response = await self._make_request(
                "GET",
                f"{self.instagram_account_id}/media",
                params={"fields": "id,caption,timestamp", "limit": 10}
            )

            if not media_response.success:
                return media_response

            all_comments = []

            # Get comments for each media
            for media in media_response.data.get("data", [])[:5]:
                comments_response = await self._make_request(
                    "GET",
                    f"{media['id']}/comments",
                    params={"fields": "id,text,timestamp,username", "limit": limit}
                )

                if comments_response.success:
                    all_comments.extend(comments_response.data.get("data", []))

            return AdapterResponse(
                success=True,
                response_code=200,
                data={"comments": all_comments[:limit], "count": len(all_comments[:limit])}
            )

        except Exception as e:
            return AdapterResponse(
                success=False,
                response_code=500,
                error=str(e)
            )

    async def get_analytics(self, post_id: Optional[str] = None) -> AdapterResponse:
        """Get media or account insights"""
        if not self.instagram_account_id:
            return AdapterResponse(
                success=False,
                response_code=400,
                error="Instagram account ID not configured"
            )

        try:
            if post_id:
                # Get media insights
                response = await self._make_request(
                    "GET",
                    f"{post_id}/insights",
                    params={
                        "metric": "engagement,impressions,reach,saved,video_views"
                    }
                )
            else:
                # Get account insights
                response = await self._make_request(
                    "GET",
                    f"{self.instagram_account_id}/insights",
                    params={
                        "metric": "impressions,reach,follower_count,profile_views",
                        "period": "day"
                    }
                )

            return response

        except Exception as e:
            return AdapterResponse(
                success=False,
                response_code=500,
                error=str(e)
            )

    async def verify_token(self) -> bool:
        """Verify access token"""
        try:
            if not self.instagram_account_id:
                return False

            response = await self._make_request(
                "GET",
                f"{self.instagram_account_id}",
                params={"fields": "id,username"}
            )
            return response.success
        except Exception:
            return False

    def get_rate_limits(self) -> Dict[str, int]:
        """Instagram Graph API rate limits"""
        return {
            "post": 25,  # 25 posts per day (approximate hourly)
            "reply": 200,  # Comment replies
            "like": 0,  # Not supported
            "follow": 0,  # Not supported
        }
