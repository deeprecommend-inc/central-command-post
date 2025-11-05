from typing import Dict, Any, Optional
import httpx
import tweepy

from .base_adapter import BaseSNSAdapter, AdapterResponse


class XAdapter(BaseSNSAdapter):
    """X (Twitter) API v2 Adapter"""

    def __init__(self, access_token: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(access_token, config)
        self.client = tweepy.Client(bearer_token=access_token)

    async def post(self, content: str, **kwargs) -> AdapterResponse:
        """
        Create a post (tweet)
        kwargs: media_ids, reply_to, quote_tweet_id, poll_options
        """
        try:
            # Prepare request parameters
            params = {
                "text": content,
            }

            if kwargs.get("media_ids"):
                params["media_ids"] = kwargs.get("media_ids")

            if kwargs.get("reply_to"):
                params["in_reply_to_tweet_id"] = kwargs.get("reply_to")

            if kwargs.get("quote_tweet_id"):
                params["quote_tweet_id"] = kwargs.get("quote_tweet_id")

            if kwargs.get("poll_options"):
                params["poll_options"] = kwargs.get("poll_options")
                params["poll_duration_minutes"] = kwargs.get("poll_duration_minutes", 1440)

            response = self.client.create_tweet(**params)

            return AdapterResponse(
                success=True,
                response_code=201,
                data={"tweet_id": response.data["id"], "text": content}
            )

        except tweepy.TweepyException as e:
            return AdapterResponse(
                success=False,
                response_code=getattr(e, "response", {}).get("status", 500),
                error=str(e)
            )

    async def reply(self, post_id: str, content: str, **kwargs) -> AdapterResponse:
        """Reply to a tweet"""
        kwargs["reply_to"] = post_id
        return await self.post(content, **kwargs)

    async def like(self, post_id: str) -> AdapterResponse:
        """Like a tweet"""
        try:
            response = self.client.like(post_id)

            return AdapterResponse(
                success=True,
                response_code=200,
                data={"tweet_id": post_id, "liked": True}
            )

        except tweepy.TweepyException as e:
            return AdapterResponse(
                success=False,
                response_code=getattr(e, "response", {}).get("status", 500),
                error=str(e)
            )

    async def follow(self, user_id: str) -> AdapterResponse:
        """Follow a user"""
        try:
            response = self.client.follow_user(user_id)

            return AdapterResponse(
                success=True,
                response_code=200,
                data={"user_id": user_id, "following": True}
            )

        except tweepy.TweepyException as e:
            return AdapterResponse(
                success=False,
                response_code=getattr(e, "response", {}).get("status", 500),
                error=str(e)
            )

    async def repost(self, post_id: str) -> AdapterResponse:
        """Retweet a tweet"""
        try:
            response = self.client.retweet(post_id)

            return AdapterResponse(
                success=True,
                response_code=200,
                data={"tweet_id": post_id, "retweeted": True}
            )

        except tweepy.TweepyException as e:
            return AdapterResponse(
                success=False,
                response_code=getattr(e, "response", {}).get("status", 500),
                error=str(e)
            )

    async def get_mentions(self, limit: int = 20) -> AdapterResponse:
        """Get mentions"""
        try:
            # Get authenticated user ID first
            me = self.client.get_me()
            user_id = me.data.id

            response = self.client.get_users_mentions(
                id=user_id,
                max_results=limit,
                tweet_fields=["created_at", "author_id", "conversation_id"]
            )

            mentions = []
            if response.data:
                for tweet in response.data:
                    mentions.append({
                        "id": tweet.id,
                        "text": tweet.text,
                        "author_id": tweet.author_id,
                        "created_at": str(tweet.created_at),
                    })

            return AdapterResponse(
                success=True,
                response_code=200,
                data={"mentions": mentions, "count": len(mentions)}
            )

        except tweepy.TweepyException as e:
            return AdapterResponse(
                success=False,
                response_code=getattr(e, "response", {}).get("status", 500),
                error=str(e)
            )

    async def get_analytics(self, post_id: Optional[str] = None) -> AdapterResponse:
        """Get tweet or account analytics"""
        try:
            if post_id:
                # Get specific tweet metrics
                response = self.client.get_tweet(
                    post_id,
                    tweet_fields=["public_metrics", "non_public_metrics", "organic_metrics"]
                )

                return AdapterResponse(
                    success=True,
                    response_code=200,
                    data={
                        "tweet_id": post_id,
                        "metrics": response.data.data
                    }
                )
            else:
                # Get user metrics
                me = self.client.get_me(user_fields=["public_metrics"])

                return AdapterResponse(
                    success=True,
                    response_code=200,
                    data={
                        "user_id": me.data.id,
                        "username": me.data.username,
                        "metrics": me.data.public_metrics
                    }
                )

        except tweepy.TweepyException as e:
            return AdapterResponse(
                success=False,
                response_code=getattr(e, "response", {}).get("status", 500),
                error=str(e)
            )

    async def verify_token(self) -> bool:
        """Verify access token"""
        try:
            self.client.get_me()
            return True
        except Exception:
            return False

    def get_rate_limits(self) -> Dict[str, int]:
        """X API rate limits (per 15 min window, converted to hourly)"""
        return {
            "post": 100,  # ~300 tweets per 3 hours
            "reply": 100,
            "like": 400,  # 1000 per 24 hours
            "follow": 160,  # 400 per 24 hours
            "repost": 100,
        }
