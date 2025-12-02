"""
Browser-use based agent service for prompt-driven browser automation
No OAuth, pure browser automation with LLM

This module integrates browser-use library for AI-driven browser automation.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from browser_use import Agent, BrowserSession, BrowserProfile, ChatAnthropic, ChatOpenAI
from browser_use.agent.views import AgentHistoryList

from app.core.config import settings

logger = logging.getLogger(__name__)


class BrowserAgentService:
    """
    Prompt-based browser automation service using browser-use

    Features:
    - Natural language task execution
    - No OAuth required
    - Browser session management
    - Cookie/storage persistence
    - Multi-platform support (YouTube, X, Instagram, TikTok)
    """

    def __init__(self):
        self.sessions: Dict[str, BrowserSession] = {}
        self._default_browser_profile = BrowserProfile(
            headless=True,
            minimum_wait_page_load_time=0.5,
            wait_between_actions=0.3,
        )

    def _get_llm(self, llm_provider: str = "anthropic"):
        """Get LLM instance based on provider"""
        if llm_provider == "openai":
            return ChatOpenAI(
                model=getattr(settings, 'OPENAI_MODEL', 'gpt-4o'),
                api_key=getattr(settings, 'OPENAI_API_KEY', None),
            )
        else:
            # Default to Anthropic
            return ChatAnthropic(
                model=getattr(settings, 'ANTHROPIC_MODEL', 'claude-sonnet-4-20250514'),
                api_key=getattr(settings, 'ANTHROPIC_API_KEY', None),
            )

    def _create_browser_profile(
        self,
        browser_config: Optional[Dict[str, Any]] = None,
        proxy: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> BrowserProfile:
        """Create browser profile with custom configuration"""
        config = browser_config or {}

        return BrowserProfile(
            headless=config.get('headless', True),
            proxy=proxy or config.get('proxy'),
            user_agent=user_agent or config.get('user_agent'),
            minimum_wait_page_load_time=config.get('minimum_wait_page_load_time', 0.5),
            wait_between_actions=config.get('wait_between_actions', 0.3),
            disable_security=config.get('disable_security', False),
        )

    async def execute_task(
        self,
        task: str,
        platform: str,
        account_credentials: Optional[Dict[str, str]] = None,
        browser_config: Optional[Dict[str, Any]] = None,
        use_cloud: bool = False,
        llm_provider: str = "anthropic",
        max_steps: int = 50,
        proxy: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute a natural language task using browser-use

        Args:
            task: Natural language task description
                  Examples:
                  - "Login to YouTube with the provided credentials"
                  - "Post a video with title 'Test' and description 'Demo'"
                  - "Like the top 5 videos in my feed"
                  - "Follow users who commented on my latest post"
            platform: SNS platform (youtube, x, instagram, tiktok)
            account_credentials: {username, email, password} for login
            browser_config: Browser settings (headless, proxy, user_agent, etc)
            use_cloud: Use Browser Use Cloud for stealth and scale
            llm_provider: LLM provider to use (anthropic, openai)
            max_steps: Maximum number of agent steps
            proxy: Proxy URL for browser
            user_agent: Custom User-Agent string

        Returns:
            {
                "success": bool,
                "result": str,
                "actions_taken": List[str],
                "screenshots": List[str],
                "execution_time": float,
                "error": Optional[str]
            }
        """
        start_time = datetime.now()
        browser_session = None

        try:
            # Build context-aware task
            full_task = self._build_task_with_context(
                task, platform, account_credentials
            )

            # Get LLM
            llm = self._get_llm(llm_provider)

            # Create browser profile
            browser_profile = self._create_browser_profile(
                browser_config=browser_config,
                proxy=proxy,
                user_agent=user_agent,
            )

            # Create browser session
            browser_session = BrowserSession(browser_profile=browser_profile)

            # Create sensitive data mapping for credentials
            sensitive_data = None
            if account_credentials:
                sensitive_data = {
                    "username": account_credentials.get('username', ''),
                    "email": account_credentials.get('email', ''),
                    "password": account_credentials.get('password', ''),
                }

            # Create and run agent
            agent = Agent(
                task=full_task,
                llm=llm,
                browser_session=browser_session,
                sensitive_data=sensitive_data,
                max_actions_per_step=3,
                use_vision=True,
            )

            # Run the agent
            history: AgentHistoryList = await agent.run(max_steps=max_steps)

            # Extract results from history
            actions_taken = []
            screenshots = []
            final_result = None

            for step in history.history:
                if step.model_output and step.model_output.action:
                    for action in step.model_output.action:
                        action_name = action.__class__.__name__
                        actions_taken.append(action_name)

                if step.state and step.state.screenshot:
                    screenshots.append(step.state.screenshot)

            # Get final result
            if history.final_result():
                final_result = history.final_result()
            elif history.history:
                last_step = history.history[-1]
                if last_step.model_output:
                    final_result = last_step.model_output.current_state.next_goal

            execution_time = (datetime.now() - start_time).total_seconds()

            return {
                "success": not history.is_stuck() and not history.has_errors(),
                "result": final_result or f"Task completed on {platform}",
                "actions_taken": actions_taken,
                "screenshots": screenshots[-5:] if screenshots else [],  # Last 5 screenshots
                "execution_time": execution_time,
                "error": None,
                "total_steps": len(history.history),
            }

        except Exception as e:
            logger.error(f"Browser agent task failed: {e}", exc_info=True)
            execution_time = (datetime.now() - start_time).total_seconds()
            return {
                "success": False,
                "result": None,
                "actions_taken": [],
                "screenshots": [],
                "execution_time": execution_time,
                "error": str(e),
            }
        finally:
            # Clean up browser session
            if browser_session:
                try:
                    await browser_session.close()
                except Exception as e:
                    logger.warning(f"Failed to close browser session: {e}")

    def _build_task_with_context(
        self,
        task: str,
        platform: str,
        credentials: Optional[Dict[str, str]]
    ) -> str:
        """Build a detailed task prompt with platform context"""

        platform_urls = {
            "youtube": "https://www.youtube.com",
            "x": "https://x.com",
            "instagram": "https://www.instagram.com",
            "tiktok": "https://www.tiktok.com",
        }

        base_url = platform_urls.get(platform.lower(), "")

        context_prompt = f"""
You are automating actions on {platform.upper()}.
Platform URL: {base_url}

"""

        if credentials:
            context_prompt += f"""
Account credentials (use for login if needed):
- Username: {{username}}
- Email: {{email}}
- Password: {{password}}

"""

        context_prompt += f"""
Task: {task}

Important:
- If not logged in, login first using the provided credentials
- Take screenshots at key steps
- Return detailed results of actions taken
- Be careful with rate limiting and CAPTCHAs
- If you encounter a CAPTCHA, report it and stop
"""

        return context_prompt

    async def login_to_platform(
        self,
        platform: str,
        username: str,
        email: str,
        password: str,
        headless: bool = True,
        proxy: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Login to a platform using browser automation

        Returns session/cookies for future use
        """

        task = f"Login to {platform} using the provided credentials. After successful login, verify that you are logged in by checking for a profile icon or username display."

        return await self.execute_task(
            task=task,
            platform=platform,
            account_credentials={
                "username": username,
                "email": email,
                "password": password,
            },
            browser_config={"headless": headless},
            proxy=proxy,
            user_agent=user_agent,
        )

    async def post_content(
        self,
        platform: str,
        content: str,
        media_urls: Optional[List[str]] = None,
        account_credentials: Optional[Dict[str, str]] = None,
        proxy: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Post content to a platform"""

        media_text = ""
        if media_urls:
            media_text = f" with media files: {', '.join(media_urls)}"

        task = f"Post the following content{media_text}: {content}"

        return await self.execute_task(
            task=task,
            platform=platform,
            account_credentials=account_credentials,
            proxy=proxy,
            user_agent=user_agent,
        )

    async def like_content(
        self,
        platform: str,
        content_url: str,
        account_credentials: Optional[Dict[str, str]] = None,
        proxy: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Like a specific piece of content"""

        task = f"Navigate to {content_url} and like it"

        return await self.execute_task(
            task=task,
            platform=platform,
            account_credentials=account_credentials,
            proxy=proxy,
            user_agent=user_agent,
        )

    async def follow_user(
        self,
        platform: str,
        user_handle: str,
        account_credentials: Optional[Dict[str, str]] = None,
        proxy: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Follow a user"""

        task = f"Navigate to @{user_handle}'s profile and follow them"

        return await self.execute_task(
            task=task,
            platform=platform,
            account_credentials=account_credentials,
            proxy=proxy,
            user_agent=user_agent,
        )

    async def comment_on_content(
        self,
        platform: str,
        content_url: str,
        comment: str,
        account_credentials: Optional[Dict[str, str]] = None,
        proxy: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Comment on a specific piece of content"""

        task = f"Navigate to {content_url} and post this comment: {comment}"

        return await self.execute_task(
            task=task,
            platform=platform,
            account_credentials=account_credentials,
            proxy=proxy,
            user_agent=user_agent,
        )

    async def search_and_interact(
        self,
        platform: str,
        search_query: str,
        interaction_type: str = "like",
        count: int = 5,
        account_credentials: Optional[Dict[str, str]] = None,
        proxy: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Search for content and interact with results"""

        task = f"""
        1. Search for "{search_query}" on {platform}
        2. {interaction_type.capitalize()} the top {count} results
        3. Report which items you interacted with
        """

        return await self.execute_task(
            task=task,
            platform=platform,
            account_credentials=account_credentials,
            proxy=proxy,
            user_agent=user_agent,
        )

    async def extract_data(
        self,
        platform: str,
        target_url: str,
        data_type: str = "comments",
        limit: int = 10,
        account_credentials: Optional[Dict[str, str]] = None,
        proxy: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Extract data from a platform page"""

        task = f"""
        Navigate to {target_url} and extract the following data:
        - Type: {data_type}
        - Limit: {limit} items

        Return the extracted data in a structured format.
        """

        return await self.execute_task(
            task=task,
            platform=platform,
            account_credentials=account_credentials,
            proxy=proxy,
            user_agent=user_agent,
        )


# Singleton instance
browser_agent = BrowserAgentService()
