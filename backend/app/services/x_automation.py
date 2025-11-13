"""
X (Twitter) ブラウザ自動化サービス
API不要、完全ブラウザ操作
"""

import asyncio
from typing import Dict, Any, Optional, List
from playwright.async_api import Page
from datetime import datetime


class XAutomationService:
    """X (Twitter) 完全自動化サービス（API不要）"""

    def __init__(self):
        self.base_url = "https://x.com"

    async def login(
        self,
        page: Page,
        username: str,
        password: str
    ) -> bool:
        """
        Xにログイン

        Returns:
            成功: True, 失敗: False
        """
        try:
            # ログインページへ
            await page.goto(f"{self.base_url}/i/flow/login")
            await asyncio.sleep(3)

            # ユーザー名入力
            username_input = page.locator('input[autocomplete="username"]')
            await username_input.fill(username)
            await asyncio.sleep(1)

            # 次へ
            next_button = page.locator('button:has-text("Next")')
            if await next_button.count() > 0:
                await next_button.click()
                await asyncio.sleep(2)

            # パスワード入力
            password_input = page.locator('input[autocomplete="current-password"]')
            await password_input.fill(password)
            await asyncio.sleep(1)

            # ログイン
            login_button = page.locator('button[data-testid="LoginForm_Login_Button"]')
            if await login_button.count() > 0:
                await login_button.click()
                await asyncio.sleep(5)

            # ログイン成功確認（ホームフィードが表示されている）
            home_timeline = page.locator('[data-testid="primaryColumn"]')
            if await home_timeline.count() > 0:
                print(f"✓ X login successful: {username}")
                return True
            else:
                print(f"✗ X login failed: {username}")
                return False

        except Exception as e:
            print(f"X login error: {e}")
            return False

    async def post_tweet(
        self,
        page: Page,
        text: str,
        media_paths: List[str] = []
    ) -> Dict[str, Any]:
        """
        ツイートを投稿

        Args:
            text: ツイート本文
            media_paths: 画像/動画ファイルパスのリスト（最大4つ）

        Returns:
            {"success": True, "tweet_url": "https://x.com/user/status/xxx"}
        """
        try:
            # ホームページへ
            await page.goto(self.base_url)
            await asyncio.sleep(3)

            # ツイート入力欄をクリック
            tweet_box = page.locator('[data-testid="tweetTextarea_0"]')
            if await tweet_box.count() > 0:
                await tweet_box.click()
                await asyncio.sleep(1)
                await tweet_box.fill(text)
                await asyncio.sleep(1)

            # メディアアップロード
            if media_paths:
                media_button = page.locator('[data-testid="fileInput"]')
                if await media_button.count() > 0:
                    for media_path in media_paths[:4]:  # 最大4つ
                        await media_button.set_input_files(media_path)
                        await asyncio.sleep(2)

            # ツイートボタン
            post_button = page.locator('[data-testid="tweetButtonInline"]')
            if await post_button.count() > 0:
                await post_button.click()
                await asyncio.sleep(3)

            # ツイートURL取得（最新のツイートから）
            # プロフィールページへ移動
            profile_button = page.locator('[data-testid="AppTabBar_Profile_Link"]')
            if await profile_button.count() > 0:
                await profile_button.click()
                await asyncio.sleep(3)

            # 最新ツイートのリンクを取得
            latest_tweet = page.locator('article[data-testid="tweet"]').first
            if await latest_tweet.count() > 0:
                tweet_link = latest_tweet.locator('a[href*="/status/"]')
                if await tweet_link.count() > 0:
                    href = await tweet_link.first.get_attribute('href')
                    tweet_url = f"{self.base_url}{href}"
                    print(f"✓ Tweet posted: {tweet_url}")
                    return {
                        "success": True,
                        "tweet_url": tweet_url
                    }

            return {"success": True, "tweet_url": None}

        except Exception as e:
            print(f"X post error: {e}")
            return {"success": False, "error": str(e)}

    async def like_tweet(
        self,
        page: Page,
        tweet_url: str
    ) -> bool:
        """
        ツイートにいいね

        Returns:
            成功: True, 失敗: False
        """
        try:
            # ツイートページへ
            await page.goto(tweet_url)
            await asyncio.sleep(3)

            # いいねボタンを探す
            like_button = page.locator('[data-testid="like"]').first
            if await like_button.count() > 0:
                await like_button.click()
                await asyncio.sleep(2)
                print(f"✓ Liked tweet: {tweet_url}")
                return True
            else:
                # すでにいいね済みの場合
                unlike_button = page.locator('[data-testid="unlike"]').first
                if await unlike_button.count() > 0:
                    print(f"ℹ Already liked: {tweet_url}")
                    return True

                print(f"✗ Could not find like button: {tweet_url}")
                return False

        except Exception as e:
            print(f"X like error: {e}")
            return False

    async def retweet(
        self,
        page: Page,
        tweet_url: str
    ) -> bool:
        """
        リツイート

        Returns:
            成功: True, 失敗: False
        """
        try:
            # ツイートページへ
            await page.goto(tweet_url)
            await asyncio.sleep(3)

            # リツイートボタンをクリック
            retweet_button = page.locator('[data-testid="retweet"]').first
            if await retweet_button.count() > 0:
                await retweet_button.click()
                await asyncio.sleep(1)

            # "Repost" を選択
            repost_option = page.locator('[data-testid="retweetConfirm"]')
            if await repost_option.count() > 0:
                await repost_option.click()
                await asyncio.sleep(2)
                print(f"✓ Retweeted: {tweet_url}")
                return True
            else:
                print(f"✗ Could not find retweet confirm button: {tweet_url}")
                return False

        except Exception as e:
            print(f"X retweet error: {e}")
            return False

    async def reply_tweet(
        self,
        page: Page,
        tweet_url: str,
        reply_text: str
    ) -> bool:
        """
        ツイートに返信

        Returns:
            成功: True, 失敗: False
        """
        try:
            # ツイートページへ
            await page.goto(tweet_url)
            await asyncio.sleep(3)

            # 返信入力欄をクリック
            reply_box = page.locator('[data-testid="tweetTextarea_0"]')
            if await reply_box.count() > 0:
                await reply_box.click()
                await asyncio.sleep(1)
                await reply_box.fill(reply_text)
                await asyncio.sleep(1)

            # 返信ボタン
            reply_button = page.locator('[data-testid="tweetButtonInline"]')
            if await reply_button.count() > 0:
                await reply_button.click()
                await asyncio.sleep(3)
                print(f"✓ Replied to tweet: {tweet_url}")
                return True
            else:
                print(f"✗ Could not find reply button: {tweet_url}")
                return False

        except Exception as e:
            print(f"X reply error: {e}")
            return False

    async def follow_user(
        self,
        page: Page,
        user_url: str
    ) -> bool:
        """
        ユーザーをフォロー

        Returns:
            成功: True, 失敗: False
        """
        try:
            # ユーザープロフィールページへ
            await page.goto(user_url)
            await asyncio.sleep(3)

            # フォローボタンを探す
            follow_button = page.locator('[data-testid*="follow"]').first
            if await follow_button.count() > 0:
                button_text = await follow_button.inner_text()

                # すでにフォロー済みかチェック
                if "Following" in button_text or "フォロー中" in button_text:
                    print(f"ℹ Already following: {user_url}")
                    return True

                await follow_button.click()
                await asyncio.sleep(2)
                print(f"✓ Followed user: {user_url}")
                return True
            else:
                print(f"✗ Could not find follow button: {user_url}")
                return False

        except Exception as e:
            print(f"X follow error: {e}")
            return False

    async def search_tweets(
        self,
        page: Page,
        query: str,
        max_results: int = 20
    ) -> List[Dict[str, str]]:
        """
        ツイートを検索

        Returns:
            [{"text": "xxx", "url": "https://...", "author": "xxx"}]
        """
        try:
            # 検索ページへ
            search_url = f"{self.base_url}/search?q={query}&src=typed_query&f=live"
            await page.goto(search_url)
            await asyncio.sleep(3)

            tweets = []
            tweet_elements = page.locator('article[data-testid="tweet"]')

            # スクロールして追加のツイートを読み込み
            for _ in range(3):
                await page.evaluate('window.scrollBy(0, 1000)')
                await asyncio.sleep(2)

            count = min(await tweet_elements.count(), max_results)

            for i in range(count):
                tweet = tweet_elements.nth(i)

                # ツイート本文
                text_elem = tweet.locator('[data-testid="tweetText"]')
                text = await text_elem.inner_text() if await text_elem.count() > 0 else ""

                # ツイートURL
                link_elem = tweet.locator('a[href*="/status/"]')
                url = ""
                if await link_elem.count() > 0:
                    href = await link_elem.first.get_attribute('href')
                    url = f"{self.base_url}{href}"

                # 著者
                author_elem = tweet.locator('[data-testid="User-Name"]')
                author = await author_elem.inner_text() if await author_elem.count() > 0 else ""

                tweets.append({
                    "text": text.strip(),
                    "url": url,
                    "author": author.strip()
                })

            print(f"✓ Found {len(tweets)} tweets for query: {query}")
            return tweets

        except Exception as e:
            print(f"X search error: {e}")
            return []

    async def get_user_info(
        self,
        page: Page,
        user_url: str
    ) -> Dict[str, Any]:
        """
        ユーザー情報を取得

        Returns:
            {"username": "xxx", "followers": "xxx", "bio": "xxx"}
        """
        try:
            await page.goto(user_url)
            await asyncio.sleep(3)

            # ユーザー名
            username_elem = page.locator('[data-testid="UserName"]')
            username = await username_elem.inner_text() if await username_elem.count() > 0 else ""

            # フォロワー数
            followers_link = page.locator('a[href$="/verified_followers"]')
            followers = ""
            if await followers_link.count() > 0:
                followers_text = await followers_link.inner_text()
                followers = followers_text.split()[0] if followers_text else ""

            # プロフィール
            bio_elem = page.locator('[data-testid="UserDescription"]')
            bio = await bio_elem.inner_text() if await bio_elem.count() > 0 else ""

            info = {
                "username": username.strip(),
                "followers": followers,
                "bio": bio.strip()
            }

            print(f"✓ User info: {info['username']} - {info['followers']} followers")
            return info

        except Exception as e:
            print(f"X user info error: {e}")
            return {}


# シングルトンインスタンス
x_automation = XAutomationService()
