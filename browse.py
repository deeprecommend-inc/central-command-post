#!/usr/bin/env python3
"""
Simple browser-use runner - No proxy, no UA rotation
Uses Playwright's Chromium with CDP connection
"""
import asyncio
import sys
import os
import subprocess
import time
import signal
import requests
from dotenv import load_dotenv

load_dotenv()

CHROME_PATH = "/root/.cache/ms-playwright/chromium-1208/chrome-linux64/chrome"
CDP_PORT = 9222


def launch_browser(headless: bool = True) -> tuple[subprocess.Popen, str]:
    """Launch Chrome with CDP and return process + websocket URL"""
    headless_arg = "--headless=new" if headless else ""
    args = [
        CHROME_PATH,
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        f"--remote-debugging-port={CDP_PORT}",
        "--remote-debugging-address=127.0.0.1",
    ]
    if headless:
        args.insert(1, "--headless=new")

    proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Wait for CDP to be ready
    for _ in range(30):
        try:
            resp = requests.get(f"http://127.0.0.1:{CDP_PORT}/json/version", timeout=1)
            data = resp.json()
            ws_url = data.get("webSocketDebuggerUrl", "")
            if ws_url:
                return proc, ws_url
        except Exception:
            pass
        time.sleep(0.5)

    proc.terminate()
    raise RuntimeError("Failed to start Chrome with CDP")


def get_llm(model: str = "gpt-4o"):
    """Get LLM based on model name"""
    if model.startswith("gpt") or model.startswith("o1") or model.startswith("o3"):
        from browser_use.llm.openai.chat import ChatOpenAI
        return ChatOpenAI(model=model)
    elif model.startswith("claude"):
        from browser_use.llm.anthropic.chat import ChatAnthropic
        return ChatAnthropic(model=model)
    else:
        from browser_use.llm.openai.chat import ChatOpenAI
        return ChatOpenAI(model=model)


async def run(task: str, headless: bool = True, model: str = "gpt-4o"):
    from browser_use import Agent
    from browser_use.browser.profile import BrowserProfile

    # Launch browser with CDP
    print(f"Launching browser (headless={headless})...")
    proc, ws_url = launch_browser(headless)
    print(f"Browser ready: {ws_url[:50]}...")

    try:
        llm = get_llm(model)
        profile = BrowserProfile(cdp_url=ws_url)
        agent = Agent(task=task, llm=llm, browser_profile=profile)

        result = await agent.run()
        print(f"\nResult: {result}")
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def main():
    if len(sys.argv) < 2:
        print("""
browser-use simple runner

Usage:
  python browse.py "<task>"
  python browse.py --show "<task>"
  python browse.py --model claude-sonnet-4-20250514 "<task>"

Options:
  --show              Show browser window (not headless)
  --model <model>     LLM model (default: gpt-4o)

Models:
  gpt-4o, gpt-4o-mini, o1, o3-mini
  claude-sonnet-4-20250514, claude-opus-4-20250514

Environment:
  OPENAI_API_KEY      Required for GPT/o1/o3 models
  ANTHROPIC_API_KEY   Required for Claude models

Examples:
  python browse.py "Go to google.com and search for python"
  python browse.py --show "Open https://example.com"
  python browse.py --model claude-sonnet-4-20250514 "Search for AI news"
""")
        sys.exit(0)

    headless = True
    model = "gpt-4o"
    args = sys.argv[1:]

    # Parse options
    filtered_args = []
    i = 0
    while i < len(args):
        if args[i] == "--show":
            headless = False
        elif args[i] == "--model" and i + 1 < len(args):
            model = args[i + 1]
            i += 1
        else:
            filtered_args.append(args[i])
        i += 1

    task = " ".join(filtered_args)
    if not task:
        print("Error: task required")
        sys.exit(1)

    asyncio.run(run(task, headless, model))


if __name__ == "__main__":
    main()
