"""
YouTube ブラウザ自動化サービス
API不要、完全ブラウザ操作
"""

import asyncio
import secrets
from typing import Dict, Any, Optional, List
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from datetime import datetime


class YouTubeAutomationService:
    """YouTube完全自動化サービス（API不要）"""

    def __init__(self):
        self.base_url = "https://www.youtube.com"

    async def login(
        self,
        page: Page,
        email: str,
        password: str
    ) -> bool:
        """
        YouTubeにログイン（Googleアカウント）

        Returns:
            成功: True, 失敗: False
        """
        try:
            # YouTubeトップページ
            await page.goto(self.base_url)
            await asyncio.sleep(2)

            # サインインボタンをクリック
            sign_in_button = page.locator('a[aria-label*="Sign in"]')
            if await sign_in_button.count() > 0:
                await sign_in_button.click()
                await asyncio.sleep(3)

            # メールアドレス入力
            email_input = page.locator('input[type="email"]')
            await email_input.fill(email)
            await asyncio.sleep(1)

            # 次へ
            await page.keyboard.press('Enter')
            await asyncio.sleep(3)

            # パスワード入力
            password_input = page.locator('input[type="password"]')
            await password_input.fill(password)
            await asyncio.sleep(1)

            # 次へ
            await page.keyboard.press('Enter')
            await asyncio.sleep(5)

            # ログイン成功確認
            # プロフィールアイコンが表示されていればログイン成功
            profile_button = page.locator('button#avatar-btn')
            if await profile_button.count() > 0:
                print(f"✓ YouTube login successful: {email}")
                return True
            else:
                print(f"✗ YouTube login failed: {email}")
                return False

        except Exception as e:
            print(f"YouTube login error: {e}")
            return False

    async def post_video(
        self,
        page: Page,
        video_path: str,
        title: str,
        description: str,
        tags: List[str] = [],
        visibility: str = "public"  # public/unlisted/private
    ) -> Dict[str, Any]:
        """
        動画をアップロード

        Args:
            video_path: ローカル動画ファイルパス
            title: タイトル
            description: 説明
            tags: タグリスト
            visibility: 公開設定

        Returns:
            {"success": True, "video_url": "https://youtube.com/watch?v=xxx"}
        """
        try:
            # YouTube Studio へ
            await page.goto("https://studio.youtube.com")
            await asyncio.sleep(3)

            # CREATE ボタンをクリック
            create_button = page.locator('button[aria-label="Create"]')
            if await create_button.count() > 0:
                await create_button.click()
                await asyncio.sleep(2)

            # Upload videos をクリック
            upload_option = page.locator('text="Upload videos"')
            if await upload_option.count() > 0:
                await upload_option.click()
                await asyncio.sleep(2)

            # ファイル選択
            file_input = page.locator('input[type="file"]')
            await file_input.set_input_files(video_path)
            await asyncio.sleep(5)

            # タイトル入力
            title_input = page.locator('#textbox')
            await title_input.first.fill(title)
            await asyncio.sleep(1)

            # 説明入力
            description_inputs = page.locator('#textbox')
            if await description_inputs.count() > 1:
                await description_inputs.nth(1).fill(description)
                await asyncio.sleep(1)

            # タグ追加（Show more をクリック）
            if tags:
                show_more = page.locator('text="Show more"')
                if await show_more.count() > 0:
                    await show_more.click()
                    await asyncio.sleep(1)

                    tags_input = page.locator('input[placeholder*="Tags"]')
                    if await tags_input.count() > 0:
                        await tags_input.fill(", ".join(tags))
                        await asyncio.sleep(1)

            # NEXT ボタン
            for _ in range(3):
                next_button = page.locator('button:has-text("Next")')
                if await next_button.count() > 0:
                    await next_button.click()
                    await asyncio.sleep(2)

            # 公開設定
            if visibility == "public":
                public_radio = page.locator('tp-yt-paper-radio-button[name="PUBLIC"]')
                if await public_radio.count() > 0:
                    await public_radio.click()
            elif visibility == "unlisted":
                unlisted_radio = page.locator('tp-yt-paper-radio-button[name="UNLISTED"]')
                if await unlisted_radio.count() > 0:
                    await unlisted_radio.click()
            elif visibility == "private":
                private_radio = page.locator('tp-yt-paper-radio-button[name="PRIVATE"]')
                if await private_radio.count() > 0:
                    await private_radio.click()

            await asyncio.sleep(1)

            # PUBLISH ボタン
            publish_button = page.locator('button:has-text("Publish")')
            if await publish_button.count() > 0:
                await publish_button.click()
                await asyncio.sleep(5)

            # 動画URLを取得
            video_link = page.locator('a[href*="/watch?v="]')
            if await video_link.count() > 0:
                video_url = await video_link.first.get_attribute('href')
                if not video_url.startswith('http'):
                    video_url = f"https://www.youtube.com{video_url}"

                print(f"✓ Video uploaded: {video_url}")
                return {
                    "success": True,
                    "video_url": video_url
                }

            return {"success": False, "error": "Could not find video URL"}

        except Exception as e:
            print(f"YouTube upload error: {e}")
            return {"success": False, "error": str(e)}

    async def like_video(
        self,
        page: Page,
        video_url: str
    ) -> bool:
        """
        動画にいいね

        Returns:
            成功: True, 失敗: False
        """
        try:
            # 動画ページへ
            await page.goto(video_url)
            await asyncio.sleep(3)

            # いいねボタンを探す
            like_button = page.locator('button[aria-label*="like this video"]')
            if await like_button.count() == 0:
                like_button = page.locator('yt-icon-button#top-level-buttons-computed > button').first

            if await like_button.count() > 0:
                await like_button.click()
                await asyncio.sleep(2)
                print(f"✓ Liked video: {video_url}")
                return True
            else:
                print(f"✗ Could not find like button: {video_url}")
                return False

        except Exception as e:
            print(f"YouTube like error: {e}")
            return False

    async def comment_video(
        self,
        page: Page,
        video_url: str,
        comment_text: str
    ) -> bool:
        """
        動画にコメント

        Returns:
            成功: True, 失敗: False
        """
        try:
            # 動画ページへ
            await page.goto(video_url)
            await asyncio.sleep(3)

            # 下にスクロールしてコメント欄を表示
            await page.evaluate('window.scrollTo(0, 800)')
            await asyncio.sleep(2)

            # コメント入力欄をクリック
            comment_box = page.locator('#placeholder-area')
            if await comment_box.count() > 0:
                await comment_box.click()
                await asyncio.sleep(1)

            # コメント入力
            comment_input = page.locator('#contenteditable-root')
            if await comment_input.count() > 0:
                await comment_input.fill(comment_text)
                await asyncio.sleep(1)

            # コメント投稿ボタン
            post_button = page.locator('button#submit-button')
            if await post_button.count() > 0:
                await post_button.click()
                await asyncio.sleep(3)
                print(f"✓ Commented on video: {video_url}")
                return True
            else:
                print(f"✗ Could not find comment button: {video_url}")
                return False

        except Exception as e:
            print(f"YouTube comment error: {e}")
            return False

    async def subscribe_channel(
        self,
        page: Page,
        channel_url: str
    ) -> bool:
        """
        チャンネル登録

        Returns:
            成功: True, 失敗: False
        """
        try:
            # チャンネルページへ
            await page.goto(channel_url)
            await asyncio.sleep(3)

            # チャンネル登録ボタンを探す
            subscribe_button = page.locator('button[aria-label*="Subscribe"]')
            if await subscribe_button.count() == 0:
                subscribe_button = page.locator('yt-subscribe-button-view-model button').first

            if await subscribe_button.count() > 0:
                # すでに登録済みかチェック
                button_text = await subscribe_button.inner_text()
                if "Subscribed" in button_text or "登録済み" in button_text:
                    print(f"ℹ Already subscribed: {channel_url}")
                    return True

                await subscribe_button.click()
                await asyncio.sleep(2)
                print(f"✓ Subscribed to channel: {channel_url}")
                return True
            else:
                print(f"✗ Could not find subscribe button: {channel_url}")
                return False

        except Exception as e:
            print(f"YouTube subscribe error: {e}")
            return False

    async def search_videos(
        self,
        page: Page,
        query: str,
        max_results: int = 10
    ) -> List[Dict[str, str]]:
        """
        動画を検索

        Returns:
            [{"title": "xxx", "url": "https://...", "channel": "xxx"}]
        """
        try:
            # 検索ページへ
            search_url = f"{self.base_url}/results?search_query={query}"
            await page.goto(search_url)
            await asyncio.sleep(3)

            videos = []
            video_elements = page.locator('ytd-video-renderer')
            count = min(await video_elements.count(), max_results)

            for i in range(count):
                video = video_elements.nth(i)

                # タイトルとURL
                title_link = video.locator('a#video-title')
                title = await title_link.inner_text()
                url = await title_link.get_attribute('href')
                if not url.startswith('http'):
                    url = f"{self.base_url}{url}"

                # チャンネル名
                channel = video.locator('ytd-channel-name a')
                channel_name = await channel.inner_text() if await channel.count() > 0 else ""

                videos.append({
                    "title": title.strip(),
                    "url": url,
                    "channel": channel_name.strip()
                })

            print(f"✓ Found {len(videos)} videos for query: {query}")
            return videos

        except Exception as e:
            print(f"YouTube search error: {e}")
            return []

    async def get_channel_info(
        self,
        page: Page,
        channel_url: str
    ) -> Dict[str, Any]:
        """
        チャンネル情報を取得

        Returns:
            {"name": "xxx", "subscribers": "xxx", "description": "xxx"}
        """
        try:
            await page.goto(channel_url)
            await asyncio.sleep(3)

            # チャンネル名
            name_elem = page.locator('yt-formatted-string#text')
            name = await name_elem.first.inner_text() if await name_elem.count() > 0 else ""

            # チャンネル登録者数
            subscribers_elem = page.locator('#subscriber-count')
            subscribers = await subscribers_elem.inner_text() if await subscribers_elem.count() > 0 else ""

            # About タブへ
            about_tab = page.locator('yt-tab-shape:has-text("About")')
            if await about_tab.count() > 0:
                await about_tab.click()
                await asyncio.sleep(2)

            # 説明
            description_elem = page.locator('yt-formatted-string#description')
            description = await description_elem.inner_text() if await description_elem.count() > 0 else ""

            info = {
                "name": name.strip(),
                "subscribers": subscribers.strip(),
                "description": description.strip()
            }

            print(f"✓ Channel info: {info['name']} - {info['subscribers']}")
            return info

        except Exception as e:
            print(f"YouTube channel info error: {e}")
            return {}


# シングルトンインスタンス
youtube_automation = YouTubeAutomationService()
