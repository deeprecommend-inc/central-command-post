"""
Browser-use based agent service for prompt-driven browser automation
No OAuth, pure browser automation with LLM

This module integrates browser-use library for AI-driven browser automation.
"""

import asyncio
import asyncio.subprocess as aio_subprocess
import logging
import base64
import sys
from typing import Dict, Any, Optional, List
from datetime import datetime

from browser_use import Agent, BrowserSession, BrowserProfile, ChatAnthropic, ChatOpenAI
from browser_use.agent.views import AgentHistoryList
from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.database import LLMSetting, LLMProviderEnum, async_session_maker

logger = logging.getLogger(__name__)


def get_encryption_key() -> bytes:
    """Get or generate encryption key for API keys"""
    key = getattr(settings, 'ENCRYPTION_KEY', None)
    if key:
        return base64.urlsafe_b64decode(key)
    secret = getattr(settings, 'SECRET_KEY', 'default-secret-key-change-me')
    return base64.urlsafe_b64encode(secret[:32].encode().ljust(32, b'0'))


def decrypt_api_key(encrypted_key: str) -> str:
    """Decrypt API key"""
    if not encrypted_key:
        return ""
    try:
        f = Fernet(get_encryption_key())
        return f.decrypt(encrypted_key.encode()).decode()
    except Exception:
        return ""


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
        self._playwright_install_lock = asyncio.Lock()
        self._playwright_ready = False
        self._playwright_deps_lock = asyncio.Lock()
        self._playwright_deps_ready = False

    async def _get_llm_settings_from_db(self, provider: str = None) -> Optional[Dict[str, Any]]:
        """Get LLM settings from database"""
        try:
            async with async_session_maker() as session:
                if provider:
                    # 指定されたプロバイダーの設定を取得
                    try:
                        provider_enum = LLMProviderEnum(provider.lower())
                    except ValueError:
                        provider_enum = None

                    if provider_enum:
                        result = await session.execute(
                            select(LLMSetting).where(
                                LLMSetting.provider == provider_enum,
                                LLMSetting.is_enabled == True
                            )
                        )
                        setting = result.scalar_one_or_none()
                        if setting and setting.api_key_encrypted:
                            # 最終使用時刻を更新
                            setting.last_used_at = datetime.utcnow()
                            await session.commit()
                            return {
                                "provider": setting.provider.value,
                                "api_key": decrypt_api_key(setting.api_key_encrypted),
                                "model": setting.default_model,
                                "api_base_url": setting.api_base_url,
                            }
                else:
                    # デフォルトプロバイダーを取得
                    result = await session.execute(
                        select(LLMSetting).where(
                            LLMSetting.is_default == True,
                            LLMSetting.is_enabled == True
                        )
                    )
                    setting = result.scalar_one_or_none()

                    if not setting:
                        # デフォルトがなければ有効な最初のプロバイダー
                        result = await session.execute(
                            select(LLMSetting).where(LLMSetting.is_enabled == True).order_by(LLMSetting.provider)
                        )
                        setting = result.scalar_one_or_none()

                    if setting and setting.api_key_encrypted:
                        setting.last_used_at = datetime.utcnow()
                        await session.commit()
                        return {
                            "provider": setting.provider.value,
                            "api_key": decrypt_api_key(setting.api_key_encrypted),
                            "model": setting.default_model,
                            "api_base_url": setting.api_base_url,
                        }

        except Exception as e:
            logger.warning(f"Failed to get LLM settings from DB: {e}")

        return None

    async def _get_llm(self, llm_provider: str = None):
        """Get LLM instance based on provider - checks DB first, then env vars"""
        # まずDBから設定を取得
        db_settings = await self._get_llm_settings_from_db(llm_provider)

        if db_settings and db_settings.get("api_key"):
            provider = db_settings["provider"]
            api_key = db_settings["api_key"]
            model = db_settings["model"]

            if provider == "openai":
                return ChatOpenAI(
                    model=model or "gpt-4o",
                    api_key=api_key,
                )
            elif provider == "anthropic":
                return ChatAnthropic(
                    model=model or "claude-sonnet-4-20250514",
                    api_key=api_key,
                )
            elif provider == "google":
                from browser_use import ChatGoogle
                return ChatGoogle(
                    model=model or "gemini-2.0-flash",
                    api_key=api_key,
                )
            elif provider == "groq":
                from browser_use import ChatGroq
                return ChatGroq(
                    model=model or "llama-3.3-70b-versatile",
                    api_key=api_key,
                )

        # DBに設定がない場合は環境変数にフォールバック
        logger.info("Using environment variables for LLM configuration")

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
        execution_log: List[str] = []

        try:
            # Build context-aware task
            full_task = self._build_task_with_context(
                task, platform, account_credentials
            )
            execution_log.append(f"Task started: {task} on {platform}")

            # Get LLM
            llm = await self._get_llm(llm_provider)
            execution_log.append(f"LLM provider: {llm_provider or 'auto'}")

            # Create browser profile
            browser_profile = self._create_browser_profile(
                browser_config=browser_config,
                proxy=proxy,
                user_agent=user_agent,
            )
            execution_log.append(
                f"Browser profile created (headless={browser_profile.headless}, proxy={'yes' if proxy else 'no'})"
            )

            # Create browser session
            browser_session = BrowserSession(browser_profile=browser_profile)
            execution_log.append("Browser session initialized")

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

            # Run the agent with auto-install retry for Playwright browsers
            history: AgentHistoryList = await self._run_agent_with_playwright_retry(
                agent,
                max_steps=max_steps,
                execution_log=execution_log,
            )
            execution_log.append(f"Agent run completed with {len(history.history)} steps")

            # Extract results from history
            actions_taken = []
            screenshots = []
            final_result = None
            step_logs: List[str] = []

            for idx, step in enumerate(history.history, 1):
                log_parts = [f"Step {idx}"]
                if step.model_output and step.model_output.action:
                    for action in step.model_output.action:
                        action_name = action.__class__.__name__
                        actions_taken.append(action_name)
                    recent_actions = actions_taken[-len(step.model_output.action):]
                    log_parts.append(f"Actions: {', '.join(recent_actions)}")
                else:
                    log_parts.append("Actions: none")

                if step.state:
                    screenshot = self._extract_screenshot(step.state)
                    if screenshot:
                        screenshots.append(screenshot)
                        log_parts.append("Screenshot captured")

                    state_summary = getattr(step.state, "state_summary", None) or getattr(
                        step.state, "description", None
                    )
                    if state_summary:
                        log_parts.append(f"State: {state_summary}")

                step_error = getattr(step, "error", None)
                if step_error:
                    log_parts.append(f"Error: {step_error}")

                step_logs.append(" | ".join(log_parts))

            # Get final result
            if history.final_result():
                final_result = history.final_result()
            elif history.history:
                last_step = history.history[-1]
                if last_step.model_output:
                    final_result = last_step.model_output.current_state.next_goal

            execution_time = (datetime.now() - start_time).total_seconds()
            execution_log.extend(step_logs)

            return {
                "success": not history.is_stuck() and not history.has_errors(),
                "result": final_result or f"Task completed on {platform}",
                "actions_taken": actions_taken,
                "screenshots": screenshots[-5:] if screenshots else [],  # Last 5 screenshots
                "execution_time": execution_time,
                "error": None,
                "execution_log": execution_log,
                "total_steps": len(history.history),
            }

        except Exception as e:
            logger.error(f"Browser agent task failed: {e}", exc_info=True)
            execution_time = (datetime.now() - start_time).total_seconds()
            error_message = str(e).strip() or e.__class__.__name__
            execution_log.append(f"Failure: {error_message}")
            return {
                "success": False,
                "result": None,
                "actions_taken": [],
                "screenshots": [],
                "execution_time": execution_time,
                "error": error_message,
                "execution_log": execution_log,
            }
        finally:
            # Clean up browser session
            if browser_session:
                try:
                    await browser_session.close()
                except Exception as e:
                    logger.warning(f"Failed to close browser session: {e}")

    async def _run_agent_with_playwright_retry(
        self,
        agent: Agent,
        max_steps: int,
        execution_log: List[str],
    ) -> AgentHistoryList:
        """
        Run the browser-use agent and auto-install Playwright browsers when missing.
        """
        retry_triggered = False
        deps_retry_triggered = False

        while True:
            try:
                return await agent.run(max_steps=max_steps)
            except FileNotFoundError as error:
                if retry_triggered or not self._should_retry_playwright_install(error):
                    raise

                retry_triggered = True
                execution_log.append(
                    "Playwright browser binaries not found. Installing chromium (one-time setup)..."
                )
                await self._install_playwright_browsers(execution_log)
                execution_log.append("Retrying task with freshly installed Playwright browsers.")
            except Exception as error:
                if deps_retry_triggered or not self._should_install_playwright_deps(error):
                    raise

                deps_retry_triggered = True
                execution_log.append(
                    "Playwright runtime dependencies missing. Installing system packages (one-time setup)..."
                )
                await self._install_playwright_dependencies(execution_log)
                execution_log.append("Retrying task after installing Playwright dependencies.")

    async def _install_playwright_browsers(self, execution_log: List[str]) -> None:
        """
        Install Playwright chromium browser binaries if they are missing.
        """
        async with self._playwright_install_lock:
            if self._playwright_ready:
                execution_log.append("Playwright chromium browser already installed, skipping setup.")
                return

            process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-m",
                "playwright",
                "install",
                "chromium",
                stdout=aio_subprocess.PIPE,
                stderr=aio_subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                message = stderr.decode().strip() or stdout.decode().strip() or "unknown error"
                execution_log.append(f"Playwright install failed: {message}")
                raise RuntimeError(f"Playwright install failed: {message}")

            self._playwright_ready = True
            execution_log.append("Playwright chromium browser installed successfully.")

    async def _install_playwright_dependencies(self, execution_log: List[str]) -> None:
        """
        Install system dependencies required by Playwright (chromium).
        """
        async with self._playwright_deps_lock:
            if self._playwright_deps_ready:
                execution_log.append("Playwright system dependencies already installed, skipping setup.")
                return

            process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-m",
                "playwright",
                "install-deps",
                "chromium",
                stdout=aio_subprocess.PIPE,
                stderr=aio_subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                message = stderr.decode().strip() or stdout.decode().strip() or "unknown error"
                execution_log.append(f"Playwright dependency install failed: {message}")
                raise RuntimeError(f"Playwright dependency install failed: {message}")

            self._playwright_deps_ready = True
            execution_log.append("Playwright system dependencies installed successfully.")

    def _should_retry_playwright_install(self, error: Exception) -> bool:
        """
        Determine if a FileNotFoundError likely comes from missing Playwright browsers.
        """
        if not isinstance(error, FileNotFoundError):
            return False

        message = str(error).lower()
        keywords = ("playwright", "ms-playwright", "chromium", "chrome")
        return any(keyword in message for keyword in keywords) or not getattr(error, "filename", None)

    def _should_install_playwright_deps(self, error: Exception) -> bool:
        """
        Determine if the exception indicates missing Playwright system dependencies.
        """
        message = str(error).lower()
        if not message:
            return False

        keywords = (
            "queueshutdown",
            "crashpad_handler",
            "libx11",
            "libxcb",
            "libnss3",
            "cannot open shared object file",
            "missing libraries",
            "renderer process crashed",
        )
        return any(keyword in message for keyword in keywords)

    def _extract_screenshot(self, state: Any) -> Optional[str]:
        """
        Safely extract a screenshot from a step state.
        Handles multiple possible attribute names and raw bytes.
        """
        candidates = [
            "screenshot",
            "screenshot_base64",
            "screenshot_png",
            "image_base64",
            "image",
        ]

        for attr in candidates:
            value = getattr(state, attr, None)
            if not value:
                continue

            if isinstance(value, bytes):
                try:
                    return base64.b64encode(value).decode("utf-8")
                except Exception:
                    continue

            if isinstance(value, str):
                return value

        return None

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
