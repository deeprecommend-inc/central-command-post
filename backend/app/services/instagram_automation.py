"""
Instagram ブラウザ自動化サービス
API不要、完全ブラウザ操作
"""

import asyncio
from typing import Dict, Any, Optional, List
from playwright.async_api import Page
from datetime import datetime


class InstagramAutomationService:
    """Instagram完全自動化サービス（API不要）"""

    def __init__(self):
        self.base_url = "https://www.instagram.com"

    async def login(
        self,
        page: Page,
        username: str,
        password: str
    ) -> bool:
        """
        Instagramにログイン

        Returns:
            成功: True, 失敗: False
        """
        try:
            # ログインページへ
            await page.goto(f"{self.base_url}/accounts/login/")
            await asyncio.sleep(3)

            # ユーザー名入力
            username_input = page.locator('input[name="username"]')
            await username_input.fill(username)
            await asyncio.sleep(1)

            # パスワード入力
            password_input = page.locator('input[name="password"]')
            await password_input.fill(password)
            await asyncio.sleep(1)

            # ログインボタン
            login_button = page.locator('button[type="submit"]')
            if await login_button.count() > 0:
                await login_button.click()
                await asyncio.sleep(5)

            # 「情報を保存しますか？」ダイアログをスキップ
            not_now_button = page.locator('button:has-text("Not Now")')
            if await not_now_button.count() > 0:
                await not_now_button.click()
                await asyncio.sleep(2)

            # 「通知をオンにする」ダイアログをスキップ
            not_now_button2 = page.locator('button:has-text("Not Now")')
            if await not_now_button2.count() > 0:
                await not_now_button2.click()
                await asyncio.sleep(2)

            # ログイン成功確認（ホームフィードが表示されている）
            home_feed = page.locator('article')
            if await home_feed.count() > 0:
                print(f"✓ Instagram login successful: {username}")
                return True
            else:
                print(f"✗ Instagram login failed: {username}")
                return False

        except Exception as e:
            print(f"Instagram login error: {e}")
            return False

    async def post_photo(
        self,
        page: Page,
        image_path: str,
        caption: str = ""
    ) -> Dict[str, Any]:
        """
        写真を投稿

        Args:
            image_path: 画像ファイルパス
            caption: キャプション

        Returns:
            {"success": True, "post_url": "https://instagram.com/p/xxx"}
        """
        try:
            # ホームページへ
            await page.goto(self.base_url)
            await asyncio.sleep(3)

            # 新規投稿ボタン（+アイコン）
            create_button = page.locator('svg[aria-label="New post"]').locator('..')
            if await create_button.count() > 0:
                await create_button.click()
                await asyncio.sleep(2)

            # ファイル選択
            file_input = page.locator('input[type="file"]')
            await file_input.set_input_files(image_path)
            await asyncio.sleep(3)

            # Next ボタン
            next_button = page.locator('button:has-text("Next")')
            if await next_button.count() > 0:
                await next_button.click()
                await asyncio.sleep(2)

            # もう一度 Next ボタン（フィルター画面）
            if await next_button.count() > 0:
                await next_button.click()
                await asyncio.sleep(2)

            # キャプション入力
            if caption:
                caption_input = page.locator('textarea[aria-label="Write a caption..."]')
                if await caption_input.count() > 0:
                    await caption_input.fill(caption)
                    await asyncio.sleep(1)

            # Share ボタン
            share_button = page.locator('button:has-text("Share")')
            if await share_button.count() > 0:
                await share_button.click()
                await asyncio.sleep(5)

            # 投稿完了確認
            # 「投稿がシェアされました」メッセージが表示される
            shared_message = page.locator('img[alt="Animated checkmark"]')
            if await shared_message.count() > 0:
                print(f"✓ Photo posted successfully")
                return {
                    "success": True,
                    "post_url": None  # Instagramは投稿直後にURLを取得しにくい
                }

            return {"success": True, "post_url": None}

        except Exception as e:
            print(f"Instagram post error: {e}")
            return {"success": False, "error": str(e)}

    async def like_post(
        self,
        page: Page,
        post_url: str
    ) -> bool:
        """
        投稿にいいね

        Returns:
            成功: True, 失敗: False
        """
        try:
            # 投稿ページへ
            await page.goto(post_url)
            await asyncio.sleep(3)

            # いいねボタンを探す
            like_button = page.locator('svg[aria-label="Like"]').locator('..')
            if await like_button.count() > 0:
                await like_button.click()
                await asyncio.sleep(2)
                print(f"✓ Liked post: {post_url}")
                return True
            else:
                # すでにいいね済みの場合
                unlike_button = page.locator('svg[aria-label="Unlike"]')
                if await unlike_button.count() > 0:
                    print(f"ℹ Already liked: {post_url}")
                    return True

                print(f"✗ Could not find like button: {post_url}")
                return False

        except Exception as e:
            print(f"Instagram like error: {e}")
            return False

    async def comment_post(
        self,
        page: Page,
        post_url: str,
        comment_text: str
    ) -> bool:
        """
        投稿にコメント

        Returns:
            成功: True, 失敗: False
        """
        try:
            # 投稿ページへ
            await page.goto(post_url)
            await asyncio.sleep(3)

            # コメント入力欄をクリック
            comment_box = page.locator('textarea[aria-label="Add a comment..."]')
            if await comment_box.count() > 0:
                await comment_box.click()
                await asyncio.sleep(1)
                await comment_box.fill(comment_text)
                await asyncio.sleep(1)

            # 投稿ボタン
            post_button = page.locator('button:has-text("Post")')
            if await post_button.count() > 0:
                await post_button.click()
                await asyncio.sleep(3)
                print(f"✓ Commented on post: {post_url}")
                return True
            else:
                print(f"✗ Could not find post button: {post_url}")
                return False

        except Exception as e:
            print(f"Instagram comment error: {e}")
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
            follow_button = page.locator('button:has-text("Follow")')
            if await follow_button.count() > 0:
                await follow_button.click()
                await asyncio.sleep(2)
                print(f"✓ Followed user: {user_url}")
                return True
            else:
                # すでにフォロー済みの場合
                following_button = page.locator('button:has-text("Following")')
                if await following_button.count() > 0:
                    print(f"ℹ Already following: {user_url}")
                    return True

                print(f"✗ Could not find follow button: {user_url}")
                return False

        except Exception as e:
            print(f"Instagram follow error: {e}")
            return False

    async def search_hashtag(
        self,
        page: Page,
        hashtag: str,
        max_results: int = 20
    ) -> List[Dict[str, str]]:
        """
        ハッシュタグで検索

        Returns:
            [{"post_url": "https://instagram.com/p/xxx", "image_url": "https://..."}]
        """
        try:
            # ハッシュタグページへ
            search_url = f"{self.base_url}/explore/tags/{hashtag}/"
            await page.goto(search_url)
            await asyncio.sleep(3)

            posts = []

            # 投稿のリンクを取得
            post_links = page.locator('a[href*="/p/"]')

            # スクロールして追加の投稿を読み込み
            for _ in range(3):
                await page.evaluate('window.scrollBy(0, 1000)')
                await asyncio.sleep(2)

            count = min(await post_links.count(), max_results)

            for i in range(count):
                link = post_links.nth(i)
                href = await link.get_attribute('href')
                post_url = f"{self.base_url}{href}"

                # サムネイル画像
                img = link.locator('img')
                image_url = ""
                if await img.count() > 0:
                    image_url = await img.first.get_attribute('src')

                posts.append({
                    "post_url": post_url,
                    "image_url": image_url
                })

            print(f"✓ Found {len(posts)} posts for hashtag: #{hashtag}")
            return posts

        except Exception as e:
            print(f"Instagram search error: {e}")
            return []

    async def get_user_info(
        self,
        page: Page,
        user_url: str
    ) -> Dict[str, Any]:
        """
        ユーザー情報を取得

        Returns:
            {"username": "xxx", "followers": "xxx", "posts": "xxx", "bio": "xxx"}
        """
        try:
            await page.goto(user_url)
            await asyncio.sleep(3)

            # ユーザー名
            username_elem = page.locator('header h2')
            username = await username_elem.inner_text() if await username_elem.count() > 0 else ""

            # 統計情報（投稿数、フォロワー数、フォロー数）
            stats = page.locator('header ul li')
            posts_count = ""
            followers_count = ""

            if await stats.count() >= 2:
                posts_elem = stats.nth(0)
                posts_count = await posts_elem.inner_text()

                followers_elem = stats.nth(1)
                followers_count = await followers_elem.inner_text()

            # プロフィール
            bio_elem = page.locator('header h1').locator('..').locator('..').locator('span')
            bio = ""
            if await bio_elem.count() > 0:
                bio = await bio_elem.first.inner_text()

            info = {
                "username": username.strip(),
                "posts": posts_count.strip(),
                "followers": followers_count.strip(),
                "bio": bio.strip()
            }

            print(f"✓ User info: {info['username']} - {info['followers']}")
            return info

        except Exception as e:
            print(f"Instagram user info error: {e}")
            return {}

    async def send_direct_message(
        self,
        page: Page,
        username: str,
        message: str
    ) -> bool:
        """
        ダイレクトメッセージを送信

        Returns:
            成功: True, 失敗: False
        """
        try:
            # メッセージページへ
            await page.goto(f"{self.base_url}/direct/inbox/")
            await asyncio.sleep(3)

            # 新規メッセージボタン
            new_message_button = page.locator('svg[aria-label="New message"]').locator('..')
            if await new_message_button.count() > 0:
                await new_message_button.click()
                await asyncio.sleep(2)

            # 受信者を検索
            search_input = page.locator('input[placeholder="Search..."]')
            if await search_input.count() > 0:
                await search_input.fill(username)
                await asyncio.sleep(2)

            # ユーザーを選択
            user_option = page.locator(f'div:has-text("{username}")').first
            if await user_option.count() > 0:
                await user_option.click()
                await asyncio.sleep(1)

            # Next ボタン
            next_button = page.locator('button:has-text("Next")')
            if await next_button.count() > 0:
                await next_button.click()
                await asyncio.sleep(2)

            # メッセージ入力
            message_input = page.locator('textarea[placeholder="Message..."]')
            if await message_input.count() > 0:
                await message_input.fill(message)
                await asyncio.sleep(1)

            # 送信ボタン
            send_button = page.locator('button:has-text("Send")')
            if await send_button.count() > 0:
                await send_button.click()
                await asyncio.sleep(2)
                print(f"✓ Sent DM to: {username}")
                return True

            print(f"✗ Could not send DM to: {username}")
            return False

        except Exception as e:
            print(f"Instagram DM error: {e}")
            return False


# シングルトンインスタンス
instagram_automation = InstagramAutomationService()
