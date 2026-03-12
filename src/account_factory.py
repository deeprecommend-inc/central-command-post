"""
Account Factory - Main orchestrator for automated account creation pipeline.

Connects all 4 layers:
  Control  (SQLite)       -> State management, resume
  Environment (GoLogin+SmartProxy) -> Browser profile, IP isolation
  Action   (Warmup/BrowserUse)     -> Cookie farming, form filling
  External (PVA)          -> SMS verification

Pipeline: pending -> warmup -> creating -> sms_wait -> sns_expand -> active
"""
import asyncio
import os
import random
import string
import time
from dataclasses import dataclass, field
from typing import Optional

from loguru import logger

from .account_db import AccountDB, AccountRecord, AccountStatus
from .warmup import WarmupEngine, WarmupConfig
from .pva import PVAManager, PVAProvider, FiveSimProvider, SMSActivateProvider


# Gmail creation prompt for browser-use agent
GMAIL_CREATE_PROMPT = """
Go to https://accounts.google.com/signup and create a new Google account:

1. Fill in the first name: {first_name}
2. Fill in the last name: {last_name}
3. Click "Next"
4. Set birth month: {birth_month}, day: {birth_day}, year: {birth_year}
5. Set gender: {gender}
6. Click "Next"
7. Choose "Create your own Gmail address"
8. Type the email: {email_prefix}
9. Click "Next"
10. Set password: {password}
11. Confirm password: {password}
12. Click "Next"
13. If phone verification is requested, enter: {phone_number}
14. Wait for SMS code and enter it when received.
15. Accept the terms and finish the setup.

Important:
- Use the exact values provided above.
- If a field requires selection from a dropdown, select the matching option.
- Take your time between actions, do not rush.
"""

SNS_SIGNUP_PROMPTS = {
    "youtube": "YouTube is already available with the Google account. Go to https://www.youtube.com and click the profile icon to verify the account is active. No additional signup needed.",
    "x": """
Go to https://x.com/i/flow/signup and create an account:
1. Click "Create account"
2. Enter name: {name}
3. Select "Use email instead" and enter: {email}
4. Set birth date: {birth_month} {birth_day}, {birth_year}
5. Click "Next" through the flow
6. Enter email verification code when prompted
7. Set password: {password}
8. Choose a username when prompted
9. Skip optional steps (profile photo, bio, follow suggestions)
""",
    "instagram": """
Go to https://www.instagram.com/accounts/emailsignup/ and create an account:
1. Enter email: {email}
2. Enter full name: {name}
3. Enter username: {username}
4. Enter password: {password}
5. Click "Sign up"
6. Set birth date: {birth_month} {birth_day}, {birth_year}
7. Enter email verification code when prompted
8. Skip optional steps
""",
    "tiktok": """
Go to https://www.tiktok.com/signup and create an account:
1. Select "Use email"
2. Set birth date: {birth_month} {birth_day}, {birth_year}
3. Enter email: {email}
4. Enter password: {password}
5. Click "Next"
6. Enter email verification code when prompted
7. Choose a username when prompted
8. Skip optional steps
""",
}


@dataclass
class FactoryConfig:
    """Account Factory configuration"""
    # Database
    db_path: str = "accounts.db"

    # Warmup
    warmup_days: int = 3
    warmup_sites_per_session: int = 5

    # Browser environment
    area: str = "us"
    headless: bool = True
    model: str = "dolphin3"
    no_proxy: bool = False

    # SmartProxy
    smartproxy_username: str = ""
    smartproxy_password: str = ""
    smartproxy_host: str = "isp.decodo.com"
    smartproxy_port: int = 10001

    # LLM
    llm_provider: str = "local"
    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = ""
    llm_timeout: int = 300

    # GoLogin
    gologin_api_token: str = ""

    # PVA
    pva_5sim_key: str = ""
    pva_sms_activate_key: str = ""

    # SNS platforms to expand to
    sns_platforms: list[str] = field(
        default_factory=lambda: ["youtube", "x", "instagram", "tiktok"]
    )

    @classmethod
    def from_env(cls) -> "FactoryConfig":
        """Load config from environment variables"""
        return cls(
            area=os.getenv("SMARTPROXY_AREA", "us"),
            headless=os.getenv("HEADLESS", "true").lower() == "true",
            model=os.getenv("LLM_MODEL", "dolphin3"),
            no_proxy=not bool(os.getenv("SMARTPROXY_USERNAME")),
            smartproxy_username=os.getenv("SMARTPROXY_USERNAME", ""),
            smartproxy_password=os.getenv("SMARTPROXY_PASSWORD", ""),
            smartproxy_host=os.getenv("SMARTPROXY_HOST", "isp.decodo.com"),
            smartproxy_port=int(os.getenv("SMARTPROXY_PORT", "10001")),
            llm_provider=os.getenv("LLM_PROVIDER", "local"),
            llm_base_url=os.getenv("LLM_BASE_URL", "http://localhost:11434/v1"),
            llm_api_key=os.getenv("LLM_API_KEY", ""),
            llm_timeout=int(os.getenv("LLM_TIMEOUT", "300")),
            gologin_api_token=os.getenv("GOLOGIN_API_TOKEN", ""),
            pva_5sim_key=os.getenv("PVA_5SIM_KEY", ""),
            pva_sms_activate_key=os.getenv("PVA_SMS_ACTIVATE_KEY", ""),
        )


def _generate_identity(area: str = "us") -> dict:
    """Generate a random identity for account creation"""
    first_names = ["James", "John", "Robert", "Michael", "David", "William",
                   "Emma", "Olivia", "Sophia", "Isabella", "Mia", "Charlotte"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia",
                  "Miller", "Davis", "Rodriguez", "Martinez", "Wilson", "Taylor"]

    first = random.choice(first_names)
    last = random.choice(last_names)
    birth_year = random.randint(1985, 2000)
    birth_month = random.randint(1, 12)
    birth_day = random.randint(1, 28)
    gender = random.choice(["Male", "Female"])

    suffix = "".join(random.choices(string.digits, k=4))
    email_prefix = f"{first.lower()}.{last.lower()}{suffix}"
    password = "".join(random.choices(
        string.ascii_letters + string.digits + "!@#$%", k=16
    ))
    username = f"{first.lower()}_{last.lower()}{suffix}"

    months = ["January", "February", "March", "April", "May", "June",
              "July", "August", "September", "October", "November", "December"]

    return {
        "first_name": first,
        "last_name": last,
        "name": f"{first} {last}",
        "email_prefix": email_prefix,
        "email": f"{email_prefix}@gmail.com",
        "password": password,
        "username": username,
        "birth_year": str(birth_year),
        "birth_month": months[birth_month - 1],
        "birth_day": str(birth_day),
        "gender": gender,
    }


class AccountFactory:
    """
    Orchestrates the full account creation pipeline.

    Usage:
        config = FactoryConfig.from_env()
        factory = AccountFactory(config)

        # Initialize 10 accounts
        factory.init_accounts(count=10)

        # Run warmup phase (call daily)
        await factory.warmup_pending()

        # Create accounts that finished warmup
        await factory.create_ready_accounts()

        # Expand to SNS platforms
        await factory.expand_sns()

        # Or run everything in one go
        await factory.run_pipeline()
    """

    def __init__(self, config: Optional[FactoryConfig] = None):
        self.config = config or FactoryConfig.from_env()
        self.db = AccountDB(self.config.db_path)
        self._pva = self._init_pva()

    def _init_pva(self) -> PVAManager:
        """Initialize PVA providers from config"""
        providers: list[PVAProvider] = []

        if self.config.pva_5sim_key:
            providers.append(FiveSimProvider(self.config.pva_5sim_key))
            logger.info("PVA provider: 5sim enabled")

        if self.config.pva_sms_activate_key:
            providers.append(SMSActivateProvider(self.config.pva_sms_activate_key))
            logger.info("PVA provider: sms-activate enabled")

        return PVAManager(providers=providers)

    def _browser_config(self, account: AccountRecord) -> dict:
        """Build browser config for an account"""
        return {
            "smartproxy_username": self.config.smartproxy_username,
            "smartproxy_password": self.config.smartproxy_password,
            "smartproxy_host": self.config.smartproxy_host,
            "smartproxy_port": self.config.smartproxy_port,
            "area": account.area or self.config.area,
            "no_proxy": self.config.no_proxy,
            "llm_provider": self.config.llm_provider,
            "llm_base_url": self.config.llm_base_url,
            "llm_api_key": self.config.llm_api_key,
            "llm_timeout": self.config.llm_timeout,
            "headless": self.config.headless,
            "use_vision": True,
            "gologin_api_token": self.config.gologin_api_token,
        }

    # -- Pipeline steps --

    def init_accounts(self, count: int = 10, area: str = "") -> list[AccountRecord]:
        """Step 0: Initialize accounts in pending state"""
        area = area or self.config.area
        accounts = self.db.create_batch(
            count=count,
            area=area,
            warmup_days=self.config.warmup_days,
        )
        logger.info(f"Initialized {count} accounts (area={area})")
        return accounts

    async def warmup_pending(self) -> int:
        """
        Step 1: Run warmup for all pending accounts.

        Transitions: pending -> warmup
        """
        pending = self.db.list_by_status(AccountStatus.PENDING)
        if not pending:
            logger.info("No pending accounts for warmup")
            return 0

        count = 0
        for account in pending:
            try:
                await self._warmup_account(account)
                count += 1
            except Exception as e:
                logger.error(f"Warmup failed for account {account.id}: {e}")
                self.db.update_status(account.id, AccountStatus.FAILED, str(e))

        return count

    async def _warmup_account(self, account: AccountRecord) -> None:
        """Run warmup for a single account"""
        session_id = f"account_{account.id}"
        profile_id = f"profile_{account.id}"
        proxy_session = f"proxy_{account.id}_{int(time.time())}"

        # Mark as warming up
        self.db.start_warmup(account.id, profile_id, proxy_session)

        # Run warmup session
        warmup_config = WarmupConfig(
            sites_per_session=self.config.warmup_sites_per_session,
            model=self.config.model,
        )

        engine = WarmupEngine(
            session_id=session_id,
            config=warmup_config,
            browser_config=self._browser_config(account),
        )

        result = await engine.run_session()

        if result.success:
            logger.info(
                f"Account {account.id} warmup session complete: "
                f"{result.sites_visited} sites, score={result.human_score}"
            )
        else:
            logger.warning(f"Account {account.id} warmup had issues: {result.error}")

    async def create_ready_accounts(self) -> int:
        """
        Step 2: Create Gmail accounts for warmup-ready profiles.

        Transitions: warmup -> creating -> sms_wait -> creating (complete)
        """
        warmup = self.db.list_by_status(AccountStatus.WARMUP)
        ready = [a for a in warmup if self.db.warmup_ready(a.id)]

        if not ready:
            logger.info("No accounts ready for creation")
            return 0

        count = 0
        for account in ready:
            try:
                await self._create_account(account)
                count += 1
            except Exception as e:
                logger.error(f"Account creation failed for {account.id}: {e}")
                self.db.update_status(account.id, AccountStatus.FAILED, str(e))

        return count

    async def _create_account(self, account: AccountRecord) -> None:
        """Create a single Gmail account"""
        from .browser_use_agent import BrowserUseConfig, BrowserUseAgent

        identity = _generate_identity(account.area)
        self.db.update_status(account.id, AccountStatus.CREATING)

        # Store identity in metadata
        self.db.update_fields(account.id, metadata=identity)
        self.db.set_email(account.id, identity["email"])

        # Request phone number from PVA
        phone_number = ""
        pva_order = None
        if self._pva._providers:
            self.db.update_status(account.id, AccountStatus.SMS_WAIT)
            pva_order = await self._pva.request_number("google", account.area)
            if pva_order:
                phone_number = pva_order.phone_number
                self.db.set_phone(account.id, phone_number)
                logger.info(f"Account {account.id}: PVA number {phone_number}")
            else:
                logger.warning(f"Account {account.id}: PVA number unavailable")

        # Build browser-use prompt
        prompt = GMAIL_CREATE_PROMPT.format(
            phone_number=phone_number,
            **identity,
        )

        # Run browser-use agent
        agent_config = BrowserUseConfig(
            smartproxy_username=self.config.smartproxy_username,
            smartproxy_password=self.config.smartproxy_password,
            smartproxy_host=self.config.smartproxy_host,
            smartproxy_port=self.config.smartproxy_port,
            area=account.area or self.config.area,
            no_proxy=self.config.no_proxy,
            llm_provider=self.config.llm_provider,
            llm_api_key=self.config.llm_api_key,
            llm_base_url=self.config.llm_base_url,
            model=self.config.model,
            headless=self.config.headless,
            use_vision=True,
            session_dir=f"./sessions/account_{account.id}",
            llm_timeout=self.config.llm_timeout,
            gologin_api_token=self.config.gologin_api_token,
        )

        agent = BrowserUseAgent(agent_config)
        result = await agent.run(prompt)

        # Wait for SMS code if PVA order is active
        if pva_order and pva_order.sms_code == "":
            code = await self._pva.wait_for_code(pva_order, timeout=120)
            if code:
                logger.info(f"Account {account.id}: SMS code received: {code}")
                # The browser-use agent should handle entering the code
                # via the prompt instructions
                await self._pva.complete(pva_order)
            else:
                logger.warning(f"Account {account.id}: SMS code timeout")

        if result.get("success"):
            self.db.update_status(account.id, AccountStatus.SNS_EXPAND)
            logger.info(f"Account {account.id}: Gmail created: {identity['email']}")
        else:
            self.db.update_status(
                account.id, AccountStatus.FAILED,
                result.get("error", "Creation failed"),
            )

    async def expand_sns(self) -> int:
        """
        Step 3: Expand created accounts to SNS platforms.

        Transitions: sns_expand -> active
        """
        accounts = self.db.list_by_status(AccountStatus.SNS_EXPAND)
        if not accounts:
            logger.info("No accounts ready for SNS expansion")
            return 0

        count = 0
        for account in accounts:
            try:
                await self._expand_account_sns(account)
                self.db.update_status(account.id, AccountStatus.ACTIVE)
                count += 1
            except Exception as e:
                logger.error(f"SNS expansion failed for {account.id}: {e}")
                self.db.update_status(account.id, AccountStatus.FAILED, str(e))

        return count

    async def _expand_account_sns(self, account: AccountRecord) -> None:
        """Register on SNS platforms for a single account"""
        from .browser_use_agent import BrowserUseConfig, BrowserUseAgent

        identity = account.metadata
        if not identity:
            raise ValueError(f"Account {account.id} has no identity metadata")

        for platform in self.config.sns_platforms:
            if platform in account.sns_accounts:
                logger.info(f"Account {account.id}: {platform} already registered")
                continue

            prompt_template = SNS_SIGNUP_PROMPTS.get(platform)
            if not prompt_template:
                logger.warning(f"No signup prompt for platform: {platform}")
                continue

            if platform == "youtube":
                # YouTube comes with Google account
                self.db.add_sns_account(account.id, "youtube", identity.get("email", ""))
                continue

            prompt = prompt_template.format(**identity)

            agent_config = BrowserUseConfig(
                smartproxy_username=self.config.smartproxy_username,
                smartproxy_password=self.config.smartproxy_password,
                smartproxy_host=self.config.smartproxy_host,
                smartproxy_port=self.config.smartproxy_port,
                area=account.area or self.config.area,
                no_proxy=self.config.no_proxy,
                llm_provider=self.config.llm_provider,
                llm_api_key=self.config.llm_api_key,
                llm_base_url=self.config.llm_base_url,
                model=self.config.model,
                headless=self.config.headless,
                use_vision=True,
                session_dir=f"./sessions/account_{account.id}",
                llm_timeout=self.config.llm_timeout,
                gologin_api_token=self.config.gologin_api_token,
            )

            agent = BrowserUseAgent(agent_config)
            result = await agent.run(prompt)

            if result.get("success"):
                username = identity.get("username", identity.get("email", ""))
                self.db.add_sns_account(account.id, platform, username)
                logger.info(f"Account {account.id}: {platform} registered")
            else:
                logger.warning(
                    f"Account {account.id}: {platform} registration failed: "
                    f"{result.get('error', 'unknown')}"
                )

            # Delay between platform signups
            await asyncio.sleep(random.uniform(30, 90))

    async def run_pipeline(self) -> dict:
        """
        Run the full pipeline: warmup -> create -> expand.

        For warmup, this only runs one session per account.
        Call warmup_pending() daily until accounts are ready.
        """
        summary = self.db.summary()
        logger.info(f"Pipeline start: {summary}")

        # Step 1: Warmup pending accounts
        warmed = await self.warmup_pending()

        # Step 2: Create accounts that finished warmup
        created = await self.create_ready_accounts()

        # Step 3: Expand to SNS
        expanded = await self.expand_sns()

        final_summary = self.db.summary()
        result = {
            "warmed_up": warmed,
            "created": created,
            "expanded": expanded,
            "summary": final_summary,
        }

        logger.info(f"Pipeline complete: {result}")
        return result

    def status(self) -> dict:
        """Get current pipeline status"""
        summary = self.db.summary()
        accounts = self.db.list_all()

        warmup_accounts = [a for a in accounts if a.status == AccountStatus.WARMUP]
        warmup_progress = {}
        for a in warmup_accounts:
            warmup_progress[a.id] = {
                "days_elapsed": round(a.warmup_elapsed_days, 1),
                "days_required": a.warmup_days,
                "ready": self.db.warmup_ready(a.id),
            }

        return {
            "summary": summary,
            "warmup_progress": warmup_progress,
            "total": len(accounts),
        }
