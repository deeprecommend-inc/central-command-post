from typing import Dict, Any, Optional
import httpx

from .base_adapter import BaseSNSAdapter, AdapterResponse


class TikTokAdapter(BaseSNSAdapter):
    """TikTok Business API Adapter"""

    def __init__(self, access_token: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(access_token, config)
        self.base_url = "https://open.tiktokapis.com/v2"

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        headers: Optional[Dict] = None
    ) -> AdapterResponse:
        """Make API request"""
        url = f"{self.base_url}/{endpoint}"

        if headers is None:
            headers = {}
        headers["Authorization"] = f"Bearer {self.access_token}"
        headers["Content-Type"] = "application/json"

        async with httpx.AsyncClient() as client:
            try:
                if method == "GET":
                    response = await client.get(url, params=params, headers=headers)
                elif method == "POST":
                    response = await client.post(url, json=data, headers=headers)
                elif method == "DELETE":
                    response = await client.delete(url, headers=headers)

                response.raise_for_status()

                json_data = response.json()

                return AdapterResponse(
                    success=json_data.get("error", {}).get("code") == "ok",
                    response_code=response.status_code,
                    data=json_data.get("data", {}),
                    error=json_data.get("error", {}).get("message")
                )

            except httpx.HTTPStatusError as e:
                return AdapterResponse(
                    success=False,
                    response_code=e.response.status_code,
                    error=str(e)
                )

    async def post(self, content: str, **kwargs) -> AdapterResponse:
        """
        Create a video post
        kwargs: video_url, title, privacy_level, disable_duet, disable_comment, disable_stitch
        """
        try:
            post_data = {
                "post_info": {
                    "title": kwargs.get("title", content[:150]),  # Max 150 chars
                    "privacy_level": kwargs.get("privacy_level", "SELF_ONLY"),  # PUBLIC_TO_EVERYONE, MUTUAL_FOLLOW_FRIENDS, SELF_ONLY
                    "disable_duet": kwargs.get("disable_duet", False),
                    "disable_comment": kwargs.get("disable_comment", False),
                    "disable_stitch": kwargs.get("disable_stitch", False),
                },
                "source_info": {
                    "source": "FILE_UPLOAD",
                    "video_url": kwargs.get("video_url"),
                }
            }

            # Add video cover if provided
            if kwargs.get("video_cover_timestamp_ms"):
                post_data["post_info"]["video_cover_timestamp_ms"] = kwargs.get("video_cover_timestamp_ms")

            response = await self._make_request(
                "POST",
                "post/publish/video/init/",
                data=post_data
            )

            return response

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
                "comment/reply/",
                data={
                    "comment_id": post_id,
                    "text": content
                }
            )

            return response

        except Exception as e:
            return AdapterResponse(
                success=False,
                response_code=500,
                error=str(e)
            )

    async def like(self, post_id: str) -> AdapterResponse:
        """Like a video (limited support)"""
        return AdapterResponse(
            success=False,
            response_code=501,
            error="Like functionality has limited support in TikTok API"
        )

    async def follow(self, user_id: str) -> AdapterResponse:
        """Follow a user (not supported)"""
        return AdapterResponse(
            success=False,
            response_code=501,
            error="Follow functionality not available in TikTok Business API"
        )

    async def get_mentions(self, limit: int = 20) -> AdapterResponse:
        """Get comments on videos"""
        try:
            # First, get user's videos
            videos_response = await self._make_request(
                "POST",
                "video/list/",
                data={
                    "max_count": 10
                }
            )

            if not videos_response.success:
                return videos_response

            all_comments = []

            # Get comments for each video
            for video in videos_response.data.get("videos", [])[:5]:
                comments_response = await self._make_request(
                    "POST",
                    "comment/list/",
                    data={
                        "video_id": video.get("id"),
                        "max_count": limit
                    }
                )

                if comments_response.success:
                    all_comments.extend(comments_response.data.get("comments", []))

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
        """Get video or user analytics"""
        try:
            if post_id:
                # Get video insights
                response = await self._make_request(
                    "POST",
                    "video/query/",
                    data={
                        "filters": {
                            "video_ids": [post_id]
                        }
                    }
                )
            else:
                # Get user info and stats
                response = await self._make_request(
                    "GET",
                    "user/info/"
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
            response = await self._make_request(
                "GET",
                "user/info/"
            )
            return response.success
        except Exception:
            return False

    def get_rate_limits(self) -> Dict[str, int]:
        """TikTok API rate limits"""
        return {
            "post": 10,  # Limited video uploads per day
            "reply": 100,  # Comment replies
            "like": 0,  # Limited support
            "follow": 0,  # Not supported
        }
