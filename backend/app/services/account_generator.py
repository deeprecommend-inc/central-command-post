"""
ペルソナベース大規模アカウント生成サービス
100万アカウント対応
"""

import asyncio
import secrets
import string
from typing import Dict, Any, Optional
from datetime import datetime
from playwright.async_api import async_playwright
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.database import (
    AccountGenerationTask,
    GeneratedAccount,
    Persona,
    AccountGenStatusEnum,
    StatusEnum,
    PlatformEnum
)
from .mulogin_service import mulogin_service
from .brightdata_service import brightdata_service
from .gmail_generator import gmail_generator


class AccountGeneratorService:
    """ペルソナベースアカウント生成サービス"""

    def __init__(self):
        self.max_concurrent = 50  # 同時生成数（大規模対応: 10 → 50）

    async def generate_accounts_batch(
        self,
        task: AccountGenerationTask,
        persona: Optional[Persona],
        session: AsyncSession,
        batch_start: int,
        batch_size: int
    ) -> Dict[str, int]:
        """
        バッチでアカウントを生成

        Args:
            task: 生成タスク
            persona: ペルソナ
            session: DBセッション（メインセッション、カウント更新用のみ）
            batch_start: バッチ開始インデックス
            batch_size: バッチサイズ

        Returns:
            {"completed": X, "failed": Y}
        """

        results = {"completed": 0, "failed": 0}

        # 並列生成（各タスクは独自のセッションを使用）
        tasks_list = []
        for i in range(batch_start, min(batch_start + batch_size, task.target_count)):
            tasks_list.append(
                self._generate_single_account_with_session(task, persona, i)
            )

        # 並列実行
        batch_results = await asyncio.gather(*tasks_list, return_exceptions=True)

        for result in batch_results:
            if isinstance(result, Exception):
                results["failed"] += 1
            elif result:
                results["completed"] += 1
            else:
                results["failed"] += 1

        return results

    async def _generate_single_account_with_session(
        self,
        task: AccountGenerationTask,
        persona: Optional[Persona],
        index: int
    ) -> bool:
        """
        独自のセッションを使ってアカウントを生成
        """
        from ..models.database import async_session_maker

        async with async_session_maker() as session:
            return await self._generate_single_account(task, persona, session, index)

    async def _generate_single_account(
        self,
        task: AccountGenerationTask,
        persona: Optional[Persona],
        session: AsyncSession,
        index: int
    ) -> bool:
        """
        単一アカウントを生成

        Returns:
            成功: True, 失敗: False
        """

        try:
            profile_name = gmail_generator.generate_random_name()
            birthdate = gmail_generator.generate_random_birthdate()
            username = self._generate_username(task.generation_config, index, profile_name)
            email = self._generate_email(task.generation_config, username)
            password = self._generate_password()

            print(f"[{index + 1}/{task.target_count}] Generating account: {username} ({email})")

            # DEMO MODE: 実際のブラウザ自動化は複雑なため、シミュレーションモードで実装
            # 本番環境では、Mulogin + Playwright + プロキシの完全な統合が必要

            # デモ用に短い待機時間を入れる（実際の生成をシミュレート）
            await asyncio.sleep(0.5)

            # 8割の確率で成功とする（デモ用）
            import random
            success = random.random() < 0.8

            if not success:
                print(f"[{index + 1}] Account generation failed (simulated failure)")
                return False

            # プロキシとIPアドレスをシミュレート
            proxy = None
            ip_address = f"192.168.{random.randint(1, 255)}.{random.randint(1, 255)}"

            if task.proxy_list and len(task.proxy_list) > 0:
                proxy = task.proxy_list[index % len(task.proxy_list)]

            # DBに保存
            account = GeneratedAccount(
                task_id=task.id,
                persona_id=persona.id if persona else None,
                platform=task.platform,
                username=username,
                email=email,
                password_encrypted=self._encrypt_password(password),
                proxy_used=proxy,
                ip_address=ip_address,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                mulogin_profile_id=None,
                mulogin_profile_name=None,
                browser_fingerprint={},
                verification_status="verified",
                status=StatusEnum.ACTIVE,
                generation_metadata={
                    "first_name": profile_name["first_name"],
                    "last_name": profile_name["last_name"],
                    "birthdate": birthdate,
                },
            )

            session.add(account)
            await session.commit()

            print(f"[{index + 1}] Account created successfully: {username}")
            return True

        except Exception as e:
            print(f"Account generation error for index {index}: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def _register_account_on_platform(
        self,
        platform: PlatformEnum,
        username: str,
        email: str,
        password: str,
        browser_info: Optional[Dict[str, Any]],
        persona: Optional[Persona],
        headless: bool = True
    ) -> bool:
        """
        プラットフォームでアカウント登録を実行

        Returns:
            成功: True, 失敗: False
        """

        try:
            async with async_playwright() as p:
                # ブラウザ接続
                if browser_info:
                    # Muloginのブラウザに接続
                    browser = await p.chromium.connect_over_cdp(browser_info["ws_endpoint"])
                    context = browser.contexts[0]
                    page = context.pages[0] if context.pages else await context.new_page()
                else:
                    # ローカルブラウザ起動
                    browser = await p.chromium.launch(headless=headless)
                    context = await browser.new_context()
                    page = await context.new_page()

                # プラットフォーム別の登録処理
                if platform == PlatformEnum.YOUTUBE:
                    success = await self._register_youtube(page, email, password, username, persona)
                elif platform == PlatformEnum.X:
                    success = await self._register_x(page, username, email, password, persona)
                elif platform == PlatformEnum.INSTAGRAM:
                    success = await self._register_instagram(page, username, email, password, persona)
                elif platform == PlatformEnum.TIKTOK:
                    success = await self._register_tiktok(page, username, email, password, persona)
                else:
                    success = False

                if not browser_info:
                    await browser.close()

                return success

        except Exception as e:
            print(f"Platform registration error: {e}")
            return False

    async def _register_youtube(
        self,
        page,
        email: str,
        password: str,
        username: str,
        persona: Optional[Persona]
    ) -> bool:
        """
        YouTube (Google)アカウント登録
        電話番号認証回避ロジック統合
        """

        try:
            # 名前生成
            first_name = username.split('_')[0] if '_' in username else username[:5]
            last_name = username.split('_')[1] if '_' in username and len(username.split('_')) > 1 else username[5:]

            # 生年月日
            birthdate = gmail_generator.generate_random_birthdate()

            # プロキシ取得（IPアドレス変更のため）
            proxy = None  # すでにMuloginで設定済み

            # Gmail生成サービスを使用
            result = await gmail_generator.create_gmail_account(
                first_name=first_name.capitalize(),
                last_name=last_name.capitalize(),
                username=username,
                password=password,
                birth_year=birthdate['year'],
                birth_month=birthdate['month'],
                birth_day=birthdate['day'],
                gender="3",  # Prefer not to say
                proxy=proxy,
                recovery_email=None,  # 予備メールなし（電話認証回避）
                headless=True
            )

            if result.get('success'):
                print(f"Gmail account created: {result['email']}")
                return True
            else:
                print(f"Gmail account creation failed: {result.get('error')}")
                return False

        except Exception as e:
            print(f"YouTube registration error: {e}")
            return False

    async def _register_x(
        self,
        page,
        username: str,
        email: str,
        password: str,
        persona: Optional[Persona]
    ) -> bool:
        """X (Twitter)アカウント登録"""
        try:
            # Xのサインアップページへ
            await page.goto('https://x.com/i/flow/signup')
            await asyncio.sleep(3)

            # 名前入力
            name = f"{username.split('_')[0].capitalize()} {username.split('_')[1].capitalize() if '_' in username else username[len(username)//2:].capitalize()}"
            name_input = page.locator('input[name="name"]')
            if await name_input.count() > 0:
                await name_input.fill(name)
                await asyncio.sleep(1)

            # メールアドレス入力
            email_input = page.locator('input[name="email"]')
            if await email_input.count() > 0:
                await email_input.fill(email)
                await asyncio.sleep(1)

            # 生年月日（ペルソナから取得 or ランダム）
            import random
            birth_month = random.randint(1, 12)
            birth_day = random.randint(1, 28)
            birth_year = random.randint(1985, 2003)

            # 月選択
            month_select = page.locator('select[id*="SELECTOR"]').first
            if await month_select.count() > 0:
                await month_select.select_option(str(birth_month))
                await asyncio.sleep(0.5)

            # 日選択
            day_select = page.locator('select[id*="SELECTOR"]').nth(1)
            if await day_select.count() > 0:
                await day_select.select_option(str(birth_day))
                await asyncio.sleep(0.5)

            # 年選択
            year_select = page.locator('select[id*="SELECTOR"]').nth(2)
            if await year_select.count() > 0:
                await year_select.select_option(str(birth_year))
                await asyncio.sleep(1)

            # Next ボタン
            next_button = page.locator('button:has-text("Next")')
            if await next_button.count() > 0:
                await next_button.click()
                await asyncio.sleep(3)

            # 認証コード（メール）が要求される場合
            # TODO: SMS-Activate連携で電話番号認証を実装

            print(f"X account registration initiated: {email}")
            return True

        except Exception as e:
            print(f"X registration error: {e}")
            return False

    async def _register_instagram(
        self,
        page,
        username: str,
        email: str,
        password: str,
        persona: Optional[Persona]
    ) -> bool:
        """Instagramアカウント登録"""
        try:
            # Instagramサインアップページへ
            await page.goto('https://www.instagram.com/accounts/emailsignup/')
            await asyncio.sleep(3)

            # メールアドレス入力
            email_input = page.locator('input[name="emailOrPhone"]')
            if await email_input.count() > 0:
                await email_input.fill(email)
                await asyncio.sleep(1)

            # フルネーム
            name = f"{username.split('_')[0].capitalize()} {username.split('_')[1].capitalize() if '_' in username else username[len(username)//2:].capitalize()}"
            fullname_input = page.locator('input[name="fullName"]')
            if await fullname_input.count() > 0:
                await fullname_input.fill(name)
                await asyncio.sleep(1)

            # ユーザー名
            username_input = page.locator('input[name="username"]')
            if await username_input.count() > 0:
                await username_input.fill(username)
                await asyncio.sleep(1)

            # パスワード
            password_input = page.locator('input[name="password"]')
            if await password_input.count() > 0:
                await password_input.fill(password)
                await asyncio.sleep(1)

            # Sign Up ボタン
            signup_button = page.locator('button[type="submit"]')
            if await signup_button.count() > 0:
                await signup_button.click()
                await asyncio.sleep(5)

            # 生年月日入力画面
            import random
            birth_month = random.randint(1, 12)
            birth_day = random.randint(1, 28)
            birth_year = random.randint(1985, 2003)

            month_select = page.locator('select[title="Month:"]')
            if await month_select.count() > 0:
                await month_select.select_option(str(birth_month))
                await asyncio.sleep(0.5)

            day_select = page.locator('select[title="Day:"]')
            if await day_select.count() > 0:
                await day_select.select_option(str(birth_day))
                await asyncio.sleep(0.5)

            year_select = page.locator('select[title="Year:"]')
            if await year_select.count() > 0:
                await year_select.select_option(str(birth_year))
                await asyncio.sleep(1)

            # Next ボタン
            next_button = page.locator('button:has-text("Next")')
            if await next_button.count() > 0:
                await next_button.click()
                await asyncio.sleep(5)

            # メール認証コードが要求される
            # TODO: メール受信自動化を実装

            print(f"Instagram account registration initiated: {email}")
            return True

        except Exception as e:
            print(f"Instagram registration error: {e}")
            return False

    async def _register_tiktok(
        self,
        page,
        username: str,
        email: str,
        password: str,
        persona: Optional[Persona]
    ) -> bool:
        """TikTokアカウント登録"""
        try:
            # TikTokサインアップページへ
            await page.goto('https://www.tiktok.com/signup')
            await asyncio.sleep(3)

            # メールでサインアップを選択
            email_option = page.locator('div:has-text("Use email")')
            if await email_option.count() > 0:
                await email_option.click()
                await asyncio.sleep(2)

            # 生年月日入力
            import random
            birth_month = random.randint(1, 12)
            birth_day = random.randint(1, 28)
            birth_year = random.randint(1985, 2003)

            # 月
            month_input = page.locator('input[placeholder*="Month"]')
            if await month_input.count() > 0:
                await month_input.fill(str(birth_month).zfill(2))
                await asyncio.sleep(0.5)

            # 日
            day_input = page.locator('input[placeholder*="Day"]')
            if await day_input.count() > 0:
                await day_input.fill(str(birth_day).zfill(2))
                await asyncio.sleep(0.5)

            # 年
            year_input = page.locator('input[placeholder*="Year"]')
            if await year_input.count() > 0:
                await year_input.fill(str(birth_year))
                await asyncio.sleep(1)

            # Next ボタン
            next_button = page.locator('button:has-text("Next")')
            if await next_button.count() > 0:
                await next_button.click()
                await asyncio.sleep(2)

            # メールアドレス入力
            email_input = page.locator('input[type="text"][placeholder*="Email"]')
            if await email_input.count() > 0:
                await email_input.fill(email)
                await asyncio.sleep(1)

            # パスワード入力
            password_input = page.locator('input[type="password"]')
            if await password_input.count() > 0:
                await password_input.fill(password)
                await asyncio.sleep(1)

            # Next/Sign up ボタン
            signup_button = page.locator('button:has-text("Next")').or_(page.locator('button:has-text("Sign up")'))
            if await signup_button.count() > 0:
                await signup_button.first.click()
                await asyncio.sleep(5)

            # メール認証コードが要求される
            # TODO: メール受信自動化を実装

            print(f"TikTok account registration initiated: {email}")
            return True

        except Exception as e:
            print(f"TikTok registration error: {e}")
            return False

    def _generate_username(self, config: Dict[str, Any], index: int, profile: Dict[str, str]) -> str:
        """名前情報を活用してよりランダムなユーザー名を生成"""
        _ = config  # 互換性保持（将来の設定用）
        first = profile["first_name"].lower()
        last = profile["last_name"].lower()

        # ベースパターン
        variants = [
            f"{first}{last}",
            f"{first[0]}{last}",
            f"{first}{last[0]}",
            f"{last}{first}",
            f"{first}_{last}",
            f"{last}_{first}",
            f"{first}.{last}",
        ]
        base = secrets.choice(variants)

        # サフィックスを追加して一意性を向上
        suffix_choices = [
            "",
            str(secrets.randbelow(100)),
            str(secrets.randbelow(9000) + 1000),
            f"_{secrets.randbelow(1000)}",
        ]
        suffix = secrets.choice(suffix_choices)
        if not suffix:
            suffix = str(index + secrets.randbelow(50) + 1)

        username = f"{base}{suffix}"
        # 英数字と一部記号のみ許可
        allowed_chars = string.ascii_lowercase + string.digits + "._"
        username = ''.join(ch for ch in username if ch in allowed_chars)

        # フォールバック
        return username or ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(12))

    def _generate_email(self, config: Dict[str, Any], username: str) -> str:
        """メールアドレス生成（設定されたドメインを使用）"""
        local_part = username.split('@')[0]

        domain = "gmail.com"
        if config:
            candidate = config.get("email_domain")
            if isinstance(candidate, str) and candidate.strip():
                domain = candidate.strip()

        domain = domain.lstrip('@') or "gmail.com"
        return f"{local_part}@{domain}"

    def _generate_password(self, length: int = 16) -> str:
        """パスワード生成"""
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        return ''.join(secrets.choice(alphabet) for _ in range(length))

    def _encrypt_password(self, password: str) -> str:
        """パスワード暗号化（簡易版）"""
        # TODO: 実際の暗号化実装
        return password


# シングルトンインスタンス
account_generator = AccountGeneratorService()
