from typing import Dict, Any, Optional
import httpx
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .base_adapter import BaseSNSAdapter, AdapterResponse


class YouTubeAdapter(BaseSNSAdapter):
    """YouTube Data API v3 Adapter"""

    def __init__(self, access_token: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(access_token, config)
        self.api_version = "v3"
        self.base_url = "https://www.googleapis.com/youtube/v3"

    async def _get_service(self):
        """Get YouTube API service"""
        credentials = Credentials(token=self.access_token)
        return build("youtube", "v3", credentials=credentials)

    async def post(self, content: str, **kwargs) -> AdapterResponse:
        """
        Create a video or community post
        kwargs: video_file, title, description, category_id, privacy_status, tags
        """
        try:
            post_type = kwargs.get("post_type", "community")  # video, shorts, community

            if post_type == "community":
                # Community post
                return await self._create_community_post(content, **kwargs)
            else:
                # Video upload (requires video file)
                return await self._upload_video(content, **kwargs)

        except HttpError as e:
            return AdapterResponse(
                success=False,
                response_code=e.resp.status,
                error=str(e)
            )

    async def _create_community_post(self, content: str, **kwargs) -> AdapterResponse:
        """Create a community post"""
        # Note: Community posts API is limited; may require workaround
        return AdapterResponse(
            success=False,
            response_code=501,
            error="Community posts API not fully supported by official API"
        )

    async def _upload_video(self, title: str, **kwargs) -> AdapterResponse:
        """Upload a video"""
        service = await self._get_service()

        body = {
            "snippet": {
                "title": title,
                "description": kwargs.get("description", ""),
                "tags": kwargs.get("tags", []),
                "categoryId": kwargs.get("category_id", "22"),
            },
            "status": {
                "privacyStatus": kwargs.get("privacy_status", "private"),
            }
        }

        try:
            request = service.videos().insert(
                part="snippet,status",
                body=body,
                media_body=kwargs.get("video_file")
            )
            response = request.execute()

            return AdapterResponse(
                success=True,
                response_code=200,
                data=response
            )
        except HttpError as e:
            return AdapterResponse(
                success=False,
                response_code=e.resp.status,
                error=str(e)
            )

    async def reply(self, post_id: str, content: str, **kwargs) -> AdapterResponse:
        """Reply to a comment or add a comment to a video"""
        try:
            service = await self._get_service()

            comment_body = {
                "snippet": {
                    "videoId": kwargs.get("video_id", post_id),
                    "topLevelComment": {
                        "snippet": {
                            "textOriginal": content
                        }
                    }
                }
            }

            # If replying to a comment
            if kwargs.get("parent_comment_id"):
                comment_body = {
                    "snippet": {
                        "parentId": kwargs.get("parent_comment_id"),
                        "textOriginal": content
                    }
                }
                request = service.comments().insert(
                    part="snippet",
                    body=comment_body
                )
            else:
                # Top-level comment on video
                request = service.commentThreads().insert(
                    part="snippet",
                    body=comment_body
                )

            response = request.execute()

            return AdapterResponse(
                success=True,
                response_code=200,
                data=response
            )

        except HttpError as e:
            return AdapterResponse(
                success=False,
                response_code=e.resp.status,
                error=str(e)
            )

    async def like(self, post_id: str) -> AdapterResponse:
        """Like a video"""
        try:
            service = await self._get_service()

            request = service.videos().rate(
                id=post_id,
                rating="like"
            )
            request.execute()

            return AdapterResponse(
                success=True,
                response_code=200,
                data={"video_id": post_id, "action": "liked"}
            )

        except HttpError as e:
            return AdapterResponse(
                success=False,
                response_code=e.resp.status,
                error=str(e)
            )

    async def follow(self, user_id: str) -> AdapterResponse:
        """Subscribe to a channel"""
        try:
            service = await self._get_service()

            body = {
                "snippet": {
                    "resourceId": {
                        "kind": "youtube#channel",
                        "channelId": user_id
                    }
                }
            }

            request = service.subscriptions().insert(
                part="snippet",
                body=body
            )
            response = request.execute()

            return AdapterResponse(
                success=True,
                response_code=200,
                data=response
            )

        except HttpError as e:
            return AdapterResponse(
                success=False,
                response_code=e.resp.status,
                error=str(e)
            )

    async def get_mentions(self, limit: int = 20) -> AdapterResponse:
        """Get comments on channel's videos"""
        try:
            service = await self._get_service()

            # Get channel's videos first
            channels_response = service.channels().list(
                part="contentDetails",
                mine=True
            ).execute()

            if not channels_response.get("items"):
                return AdapterResponse(
                    success=False,
                    response_code=404,
                    error="No channel found"
                )

            # Get comments
            request = service.commentThreads().list(
                part="snippet",
                allThreadsRelatedToChannelId=channels_response["items"][0]["id"],
                maxResults=limit,
                order="time"
            )
            response = request.execute()

            return AdapterResponse(
                success=True,
                response_code=200,
                data=response
            )

        except HttpError as e:
            return AdapterResponse(
                success=False,
                response_code=e.resp.status,
                error=str(e)
            )

    async def get_analytics(self, post_id: Optional[str] = None) -> AdapterResponse:
        """Get video or channel analytics"""
        try:
            service = await self._get_service()

            if post_id:
                # Get specific video stats
                request = service.videos().list(
                    part="statistics",
                    id=post_id
                )
            else:
                # Get channel stats
                request = service.channels().list(
                    part="statistics",
                    mine=True
                )

            response = request.execute()

            return AdapterResponse(
                success=True,
                response_code=200,
                data=response
            )

        except HttpError as e:
            return AdapterResponse(
                success=False,
                response_code=e.resp.status,
                error=str(e)
            )

    async def verify_token(self) -> bool:
        """Verify access token"""
        try:
            service = await self._get_service()
            service.channels().list(part="snippet", mine=True).execute()
            return True
        except Exception:
            return False

    def get_rate_limits(self) -> Dict[str, int]:
        """YouTube API quota limits (per day, converted to hourly approximation)"""
        return {
            "post": 60,  # Video uploads
            "reply": 200,  # Comments
            "like": 500,  # Rating
            "follow": 100,  # Subscriptions
        }
