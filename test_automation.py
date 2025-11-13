"""
ブラウザ自動化のテストスクリプト

使用方法:
    python test_automation.py --platform youtube --action test_gmail
    python test_automation.py --platform youtube --action login --email xxx@gmail.com --password xxx
    python test_automation.py --platform youtube --action like --video-url https://youtube.com/watch?v=xxx
"""

import asyncio
import argparse
import sys
import os

# バックエンドのパスを追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from playwright.async_api import async_playwright
from app.services.gmail_generator import gmail_generator
from app.services.youtube_automation import youtube_automation
from app.services.x_automation import x_automation
from app.services.instagram_automation import instagram_automation
from app.services.mulogin_service import mulogin_service
from app.services.brightdata_service import brightdata_service


async def test_gmail_generation():
    """Gmail生成テスト"""
    print("=" * 60)
    print("Gmail Generation Test")
    print("=" * 60)

    # ランダムな名前とユーザー名を生成
    names = gmail_generator.generate_random_name()
    birthdate = gmail_generator.generate_random_birthdate()
    username = gmail_generator.generate_username(names['first_name'], names['last_name'])
    password = gmail_generator.generate_password()

    print(f"Name: {names['first_name']} {names['last_name']}")
    print(f"Username: {username}")
    print(f"Birthdate: {birthdate['year']}-{birthdate['month']}-{birthdate['day']}")
    print(f"Password: {password}")
    print()

    # プロキシテスト（オプション）
    # proxy = "your_proxy_here"  # user:pass@host:port

    # Gmailアカウント作成
    result = await gmail_generator.create_gmail_account(
        first_name=names['first_name'],
        last_name=names['last_name'],
        username=username,
        password=password,
        birth_year=birthdate['year'],
        birth_month=birthdate['month'],
        birth_day=birthdate['day'],
        proxy=None,  # プロキシを使う場合はここに設定
        headless=False  # ブラウザを表示する
    )

    if result['success']:
        print(f"✓ SUCCESS: Gmail account created!")
        print(f"  Email: {result['email']}")
        print(f"  Password: {result['password']}")
    else:
        print(f"✗ FAILED: {result.get('error')}")


async def test_youtube_login(email: str, password: str):
    """YouTubeログインテスト"""
    print("=" * 60)
    print("YouTube Login Test")
    print("=" * 60)
    print(f"Email: {email}")
    print()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        success = await youtube_automation.login(page, email, password)

        if success:
            print(f"✓ SUCCESS: Logged in to YouTube")
            await asyncio.sleep(5)  # 画面を確認
        else:
            print(f"✗ FAILED: Login failed")

        await browser.close()


async def test_youtube_like(email: str, password: str, video_url: str):
    """YouTube いいねテスト"""
    print("=" * 60)
    print("YouTube Like Test")
    print("=" * 60)
    print(f"Video: {video_url}")
    print()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        # ログイン
        print("Logging in...")
        await youtube_automation.login(page, email, password)

        # いいね
        print("Liking video...")
        success = await youtube_automation.like_video(page, video_url)

        if success:
            print(f"✓ SUCCESS: Liked video")
        else:
            print(f"✗ FAILED: Could not like video")

        await asyncio.sleep(5)
        await browser.close()


async def test_youtube_comment(email: str, password: str, video_url: str, comment: str):
    """YouTube コメントテスト"""
    print("=" * 60)
    print("YouTube Comment Test")
    print("=" * 60)
    print(f"Video: {video_url}")
    print(f"Comment: {comment}")
    print()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        # ログイン
        print("Logging in...")
        await youtube_automation.login(page, email, password)

        # コメント
        print("Commenting...")
        success = await youtube_automation.comment_video(page, video_url, comment)

        if success:
            print(f"✓ SUCCESS: Commented on video")
        else:
            print(f"✗ FAILED: Could not comment")

        await asyncio.sleep(5)
        await browser.close()


async def test_youtube_subscribe(email: str, password: str, channel_url: str):
    """YouTube チャンネル登録テスト"""
    print("=" * 60)
    print("YouTube Subscribe Test")
    print("=" * 60)
    print(f"Channel: {channel_url}")
    print()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        # ログイン
        print("Logging in...")
        await youtube_automation.login(page, email, password)

        # チャンネル登録
        print("Subscribing...")
        success = await youtube_automation.subscribe_channel(page, channel_url)

        if success:
            print(f"✓ SUCCESS: Subscribed to channel")
        else:
            print(f"✗ FAILED: Could not subscribe")

        await asyncio.sleep(5)
        await browser.close()


async def test_x_login(username: str, password: str):
    """X (Twitter) ログインテスト"""
    print("=" * 60)
    print("X (Twitter) Login Test")
    print("=" * 60)
    print(f"Username: {username}")
    print()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        success = await x_automation.login(page, username, password)

        if success:
            print(f"✓ SUCCESS: Logged in to X")
            await asyncio.sleep(5)
        else:
            print(f"✗ FAILED: Login failed")

        await browser.close()


async def test_x_post(username: str, password: str, text: str):
    """X (Twitter) ツイートテスト"""
    print("=" * 60)
    print("X (Twitter) Post Test")
    print("=" * 60)
    print(f"Text: {text}")
    print()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        # ログイン
        print("Logging in...")
        await x_automation.login(page, username, password)

        # ツイート
        print("Posting tweet...")
        result = await x_automation.post_tweet(page, text)

        if result['success']:
            print(f"✓ SUCCESS: Tweet posted")
            if result.get('tweet_url'):
                print(f"  URL: {result['tweet_url']}")
        else:
            print(f"✗ FAILED: Could not post tweet")

        await asyncio.sleep(5)
        await browser.close()


async def test_instagram_login(username: str, password: str):
    """Instagram ログインテスト"""
    print("=" * 60)
    print("Instagram Login Test")
    print("=" * 60)
    print(f"Username: {username}")
    print()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        success = await instagram_automation.login(page, username, password)

        if success:
            print(f"✓ SUCCESS: Logged in to Instagram")
            await asyncio.sleep(5)
        else:
            print(f"✗ FAILED: Login failed")

        await browser.close()


async def test_proxy():
    """プロキシテスト"""
    print("=" * 60)
    print("Proxy Test")
    print("=" * 60)

    # BrightData レジデンシャルプロキシ
    proxy = brightdata_service.get_residential_proxy(
        country="us",
        city="newyork",
        session_id="test_session_1"
    )

    print(f"Proxy URL: {proxy}")
    print()

    # プロキシテスト
    result = await brightdata_service.test_proxy(proxy)

    if result.get('success'):
        print(f"✓ Proxy is working!")
        print(f"  IP: {result.get('ip')}")
        print(f"  Country: {result.get('country')}")
        print(f"  City: {result.get('city')}")
        print(f"  ISP: {result.get('isp')}")
    else:
        print(f"✗ Proxy test failed: {result.get('error')}")


def main():
    parser = argparse.ArgumentParser(description='SNS Automation Test Script')
    parser.add_argument('--platform', choices=['youtube', 'x', 'instagram', 'proxy'], required=True,
                        help='Platform to test')
    parser.add_argument('--action', required=True,
                        help='Action to perform (login, like, comment, subscribe, post, test_gmail)')
    parser.add_argument('--email', help='Email address')
    parser.add_argument('--username', help='Username')
    parser.add_argument('--password', help='Password')
    parser.add_argument('--video-url', help='YouTube video URL')
    parser.add_argument('--channel-url', help='YouTube channel URL')
    parser.add_argument('--tweet-url', help='X tweet URL')
    parser.add_argument('--text', help='Text to post')
    parser.add_argument('--comment', help='Comment text')

    args = parser.parse_args()

    # テスト実行
    if args.platform == 'youtube':
        if args.action == 'test_gmail':
            asyncio.run(test_gmail_generation())
        elif args.action == 'login':
            if not args.email or not args.password:
                print("Error: --email and --password required")
                return
            asyncio.run(test_youtube_login(args.email, args.password))
        elif args.action == 'like':
            if not args.email or not args.password or not args.video_url:
                print("Error: --email, --password, and --video-url required")
                return
            asyncio.run(test_youtube_like(args.email, args.password, args.video_url))
        elif args.action == 'comment':
            if not args.email or not args.password or not args.video_url or not args.comment:
                print("Error: --email, --password, --video-url, and --comment required")
                return
            asyncio.run(test_youtube_comment(args.email, args.password, args.video_url, args.comment))
        elif args.action == 'subscribe':
            if not args.email or not args.password or not args.channel_url:
                print("Error: --email, --password, and --channel-url required")
                return
            asyncio.run(test_youtube_subscribe(args.email, args.password, args.channel_url))

    elif args.platform == 'x':
        if args.action == 'login':
            if not args.username or not args.password:
                print("Error: --username and --password required")
                return
            asyncio.run(test_x_login(args.username, args.password))
        elif args.action == 'post':
            if not args.username or not args.password or not args.text:
                print("Error: --username, --password, and --text required")
                return
            asyncio.run(test_x_post(args.username, args.password, args.text))

    elif args.platform == 'instagram':
        if args.action == 'login':
            if not args.username or not args.password:
                print("Error: --username and --password required")
                return
            asyncio.run(test_instagram_login(args.username, args.password))

    elif args.platform == 'proxy':
        asyncio.run(test_proxy())


if __name__ == '__main__':
    main()
