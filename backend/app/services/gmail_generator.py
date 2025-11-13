"""
電話番号認証を回避したGmailアカウント自動生成サービス

戦略:
1. モバイルUser-Agent使用
2. シークレットモード（Cookieなし）
3. プロキシローテーション（IPアドレス変更）
4. 異なる氏名・パスワード・予備メール
5. レジデンシャルプロキシ（モバイルIPが最適）
"""

import asyncio
import secrets
import string
from typing import Dict, Any, Optional
from datetime import datetime
from playwright.async_api import async_playwright, Page, Browser, BrowserContext


class GmailGeneratorService:
    """電話番号認証を回避したGmail生成サービス"""

    def __init__(self):
        self.mobile_user_agents = [
            # iPhone
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 15_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.5 Mobile/15E148 Safari/604.1",

            # Android
            "Mozilla/5.0 (Linux; Android 13; SM-S901B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Mozilla/5.0 (Linux; Android 12; Pixel 6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36",
        ]

    async def create_gmail_account(
        self,
        first_name: str,
        last_name: str,
        username: str,
        password: str,
        birth_year: int,
        birth_month: int,
        birth_day: int,
        gender: str = "3",  # 3 = Prefer not to say
        proxy: Optional[str] = None,
        recovery_email: Optional[str] = None,
        headless: bool = True
    ) -> Dict[str, Any]:
        """
        電話番号認証なしでGmailアカウント作成

        戦略:
        - モバイルUser-Agent
        - シークレットモード
        - プロキシでIP変更
        - 異なる情報使用

        Returns:
            {"success": True, "email": "xxx@gmail.com", "password": "xxx"}
        """

        try:
            async with async_playwright() as p:
                # モバイルUser-Agentを選択
                mobile_ua = secrets.choice(self.mobile_user_agents)

                # ブラウザ設定（モバイルエミュレーション）
                browser_args = [
                    '--disable-blink-features=AutomationControlled',
                    '--disable-features=IsolateOrigins,site-per-process',
                    '--disable-site-isolation-trials',
                ]

                # プロキシ設定
                proxy_config = None
                if proxy:
                    proxy_parts = self._parse_proxy(proxy)
                    proxy_config = {
                        "server": f"http://{proxy_parts['host']}:{proxy_parts['port']}",
                    }
                    if proxy_parts.get('username'):
                        proxy_config["username"] = proxy_parts['username']
                        proxy_config["password"] = proxy_parts['password']

                # ブラウザ起動
                browser = await p.chromium.launch(
                    headless=headless,
                    args=browser_args,
                    proxy=proxy_config
                )

                # シークレットモード（Cookieなし）
                context = await browser.new_context(
                    user_agent=mobile_ua,
                    viewport={'width': 390, 'height': 844},  # iPhone 13 Pro
                    device_scale_factor=3,
                    is_mobile=True,
                    has_touch=True,
                    locale='en-US',
                    timezone_id='America/New_York',
                    permissions=['geolocation'],
                    geolocation={'latitude': 40.7128, 'longitude': -74.0060},  # NY
                    ignore_https_errors=True
                )

                page = await context.new_page()

                # Gmailアカウント作成ページへ
                await page.goto('https://accounts.google.com/signup/v2/createaccount?flowName=GlifWebSignIn&flowEntry=SignUp')

                # ページ読み込み待機
                await page.wait_for_load_state('networkidle')
                await asyncio.sleep(2)

                # 名前入力
                await self._fill_input(page, 'input[name="firstName"]', first_name)
                await asyncio.sleep(0.5)
                await self._fill_input(page, 'input[name="lastName"]', last_name)
                await asyncio.sleep(1)

                # 「次へ」ボタン
                await self._click_next(page)
                await asyncio.sleep(3)

                # 生年月日と性別
                await self._fill_input(page, 'input[name="day"]', str(birth_day))
                await asyncio.sleep(0.5)

                # 月選択
                await page.select_option('select#month', str(birth_month))
                await asyncio.sleep(0.5)

                await self._fill_input(page, 'input[name="year"]', str(birth_year))
                await asyncio.sleep(0.5)

                # 性別選択
                await page.select_option('select#gender', gender)
                await asyncio.sleep(1)

                # 「次へ」
                await self._click_next(page)
                await asyncio.sleep(3)

                # ユーザー名選択画面
                # 「独自のGmailアドレスを作成」をクリック
                create_own_button = page.locator('text=Create your own Gmail address')
                if await create_own_button.count() > 0:
                    await create_own_button.click()
                    await asyncio.sleep(2)

                # ユーザー名入力
                await self._fill_input(page, 'input[name="Username"]', username)
                await asyncio.sleep(1)

                # 「次へ」
                await self._click_next(page)
                await asyncio.sleep(3)

                # パスワード入力
                await self._fill_input(page, 'input[name="Passwd"]', password)
                await asyncio.sleep(0.5)
                await self._fill_input(page, 'input[name="PasswdAgain"]', password)
                await asyncio.sleep(1)

                # 「次へ」
                await self._click_next(page)
                await asyncio.sleep(3)

                # 電話番号スキップ
                # 「スキップ」ボタンを探す
                skip_button = page.locator('button:has-text("Skip")')
                if await skip_button.count() > 0:
                    await skip_button.click()
                    await asyncio.sleep(2)

                # 予備のメールアドレス（オプション）
                if recovery_email:
                    recovery_input = page.locator('input[name="recovery"]')
                    if await recovery_input.count() > 0:
                        await self._fill_input(page, 'input[name="recovery"]', recovery_email)
                        await asyncio.sleep(1)

                # スキップまたは次へ
                await self._click_next(page)
                await asyncio.sleep(3)

                # 利用規約
                # 下にスクロール
                await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                await asyncio.sleep(2)

                # 「同意する」ボタン
                agree_button = page.locator('button:has-text("I agree")')
                if await agree_button.count() > 0:
                    await agree_button.click()
                    await asyncio.sleep(3)

                # アカウント作成成功を確認
                await page.wait_for_url('https://myaccount.google.com/**', timeout=15000)

                email = f"{username}@gmail.com"

                await browser.close()

                return {
                    "success": True,
                    "email": email,
                    "password": password,
                    "username": username,
                    "first_name": first_name,
                    "last_name": last_name
                }

        except Exception as e:
            print(f"Gmail account creation error: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _fill_input(self, page: Page, selector: str, value: str):
        """入力フィールドに値を入力"""
        try:
            await page.wait_for_selector(selector, timeout=5000)
            await page.fill(selector, value)
        except Exception as e:
            print(f"Fill input error for {selector}: {e}")

    async def _click_next(self, page: Page):
        """「次へ」ボタンをクリック"""
        try:
            # 複数の「次へ」ボタンパターンに対応
            next_selectors = [
                'button:has-text("Next")',
                'button span:has-text("Next")',
                'button[jsname="LgbsSe"]',
                'button.VfPpkd-LgbsSe'
            ]

            for selector in next_selectors:
                button = page.locator(selector)
                if await button.count() > 0:
                    await button.first.click()
                    return

        except Exception as e:
            print(f"Click next error: {e}")

    def _parse_proxy(self, proxy: str) -> Dict[str, str]:
        """プロキシ文字列をパース"""
        import re

        # user:pass@host:port
        auth_match = re.match(r'^([^:]+):([^@]+)@([^:]+):(\d+)$', proxy)
        if auth_match:
            return {
                "username": auth_match.group(1),
                "password": auth_match.group(2),
                "host": auth_match.group(3),
                "port": auth_match.group(4)
            }

        # host:port
        simple_match = re.match(r'^([^:]+):(\d+)$', proxy)
        if simple_match:
            return {
                "host": simple_match.group(1),
                "port": simple_match.group(2)
            }

        raise ValueError(f"Invalid proxy format: {proxy}")

    def generate_random_name(self) -> Dict[str, str]:
        """ランダムな名前を生成"""
        first_names = [
            "James", "John", "Robert", "Michael", "William",
            "David", "Richard", "Joseph", "Thomas", "Charles",
            "Mary", "Patricia", "Jennifer", "Linda", "Elizabeth",
            "Barbara", "Susan", "Jessica", "Sarah", "Karen"
        ]

        last_names = [
            "Smith", "Johnson", "Williams", "Brown", "Jones",
            "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
            "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
            "Thomas", "Taylor", "Moore", "Jackson", "Martin"
        ]

        return {
            "first_name": secrets.choice(first_names),
            "last_name": secrets.choice(last_names)
        }

    def generate_random_birthdate(self) -> Dict[str, int]:
        """ランダムな生年月日を生成（18歳以上）"""
        import random

        year = random.randint(1970, 2005)
        month = random.randint(1, 12)
        day = random.randint(1, 28)

        return {
            "year": year,
            "month": month,
            "day": day
        }

    def generate_username(self, first_name: str, last_name: str, index: int = 0) -> str:
        """ユーザー名を生成"""
        base = f"{first_name.lower()}{last_name.lower()}"

        if index > 0:
            base += str(index)
        else:
            # ランダムな数字を追加
            base += str(secrets.randbelow(10000))

        return base

    def generate_password(self, length: int = 16) -> str:
        """強力なパスワードを生成"""
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        return ''.join(secrets.choice(alphabet) for _ in range(length))


# シングルトンインスタンス
gmail_generator = GmailGeneratorService()
