#!/usr/bin/env python3
"""
Run Web Agent - Simplified CLI entry point

Usage:
  python run.py [options] "<prompt>"

Options:
  --model, -m     LLM model (default: env LLM_MODEL or dolphin3)
  --parallel, -p  Parallel workers (default: 1)
  --area, -a      Country code (default: env SMARTPROXY_AREA or us)
  --timezone, -t  Timezone override (default: auto from area)
  --no-proxy      Direct connection
"""
import asyncio
import sys
import os
from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

# Configure logging
from src.logging_config import configure_logging

json_logging = os.getenv("LOG_FORMAT", "").lower() == "json"
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
configure_logging(level=log_level, json_format=json_logging)

from loguru import logger


def get_env(key: str, default: str = "") -> str:
    return os.getenv(key, default) or default


def parse_args(args: list[str]) -> dict:
    """Parse command line arguments"""
    opts = {
        "model": get_env("LLM_MODEL", "dolphin3"),
        "parallel": 1,
        "area": get_env("SMARTPROXY_AREA", "us"),
        "timezone": get_env("SMARTPROXY_TIMEZONE", ""),
        "no_proxy": False,
        "mode": "browser-use",
        "prompt_parts": [],
        "verbose": False,
    }

    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("--model", "-m") and i + 1 < len(args):
            i += 1
            opts["model"] = args[i]
        elif arg in ("--parallel", "-p") and i + 1 < len(args):
            i += 1
            opts["parallel"] = int(args[i])
        elif arg in ("--area", "-a") and i + 1 < len(args):
            i += 1
            opts["area"] = args[i]
        elif arg in ("--timezone", "-t") and i + 1 < len(args):
            i += 1
            opts["timezone"] = args[i]
        elif arg in ("--mode", "-M") and i + 1 < len(args):
            i += 1
            opts["mode"] = args[i]
        elif arg == "--no-proxy":
            opts["no_proxy"] = True
        elif arg in ("--verbose", "-v"):
            opts["verbose"] = True
        elif arg in ("-h", "--help", "help"):
            print_usage()
            sys.exit(0)
        else:
            opts["prompt_parts"].append(arg)
        i += 1

    return opts


async def run(opts: dict):
    """Run browser agent with given options"""
    from src.browser_use_agent import BrowserUseAgent, BrowserUseConfig

    prompt = " ".join(opts["prompt_parts"])
    if not prompt:
        print_usage()
        sys.exit(1)

    # Resolve LLM provider
    llm_provider = get_env("LLM_PROVIDER", "local")
    llm_base_url = get_env("LLM_BASE_URL", "http://localhost:11434/v1")
    llm_api_key = get_env("LLM_API_KEY") or get_env("OPENAI_API_KEY")

    if llm_provider != "local" and not llm_api_key:
        logger.error("API key required (set LLM_API_KEY, or set LLM_PROVIDER=local)")
        sys.exit(1)

    config = BrowserUseConfig(
        smartproxy_username=get_env("SMARTPROXY_USERNAME"),
        smartproxy_password=get_env("SMARTPROXY_PASSWORD"),
        smartproxy_host=get_env("SMARTPROXY_HOST", "isp.decodo.com"),
        smartproxy_port=int(get_env("SMARTPROXY_PORT", "10001")),
        area=opts["area"],
        timezone=opts["timezone"],
        no_proxy=opts["no_proxy"],
        llm_provider=llm_provider,
        llm_api_key=llm_api_key,
        llm_base_url=llm_base_url,
        model=opts["model"],
        headless=get_env("HEADLESS", "true").lower() == "true",
        use_vision=get_env("USE_VISION", "true").lower() == "true",
        session_dir=get_env("SESSION_DIR", ""),
        llm_timeout=int(get_env("LLM_TIMEOUT", "300")),
        step_timeout=int(get_env("STEP_TIMEOUT", "600")),
        gologin_api_token=get_env("GOLOGIN_API_TOKEN"),
    )

    agent = BrowserUseAgent(config)

    parallel = opts["parallel"]
    if parallel > 1:
        tasks = [prompt] * parallel
        results = await agent.run_parallel(tasks, max_concurrent=parallel)
        success_count = sum(1 for r in results if r.get("success"))
        logger.info(f"Completed: {success_count}/{len(tasks)} tasks successful")
        if success_count < len(tasks):
            sys.exit(1)
    else:
        result = await agent.run(prompt)
        if result.get("success"):
            logger.info("Task completed successfully")
        else:
            logger.error(f"Task failed: {result.get('error')}")
            sys.exit(1)

        # Display human score
        hs = result.get("human_score")
        if hs:
            score = hs.get("score", 0)
            max_score = hs.get("max", 100)
            verdict = "PASS" if hs.get("is_human", False) else "FAIL"
            print(f"\nHuman Score: {score}/{max_score} [{verdict}]")


async def run_scrapling(opts: dict):
    """Run scrapling stealth fetch with given options"""
    from src.scrapling_agent import ScraplingAgent, ScraplingConfig

    prompt = " ".join(opts["prompt_parts"])
    if not prompt:
        print_usage()
        sys.exit(1)

    config = ScraplingConfig(
        smartproxy_username=get_env("SMARTPROXY_USERNAME"),
        smartproxy_password=get_env("SMARTPROXY_PASSWORD"),
        smartproxy_host=get_env("SMARTPROXY_HOST", "isp.decodo.com"),
        smartproxy_port=int(get_env("SMARTPROXY_PORT", "10001")),
        area=opts["area"],
        timezone=opts["timezone"],
        no_proxy=opts["no_proxy"],
        headless=get_env("HEADLESS", "true").lower() == "true",
        solve_cloudflare=get_env("SOLVE_CLOUDFLARE", "false").lower() == "true",
        gologin_api_token=get_env("GOLOGIN_API_TOKEN"),
    )

    agent = ScraplingAgent(config)

    parallel = opts["parallel"]
    if parallel > 1:
        tasks = [prompt] * parallel
        results = await agent.run_parallel(tasks, max_concurrent=parallel)
        success_count = sum(1 for r in results if r.get("success"))
        logger.info(f"Completed: {success_count}/{len(tasks)} tasks successful")
        if success_count < len(tasks):
            sys.exit(1)
    else:
        result = await agent.run(prompt)
        if result.get("success"):
            logger.info("Scrapling fetch completed successfully")
            r = result.get("result", {})
            if isinstance(r, dict):
                print(f"\nURL: {r.get('url', '')}")
                print(f"Title: {r.get('title', '')}")
                print(f"Status: {r.get('status', '')}")
                print(f"Text length: {r.get('text_length', 0)}")
        else:
            logger.error(f"Scrapling fetch failed: {result.get('error')}")
            sys.exit(1)

        # Display human score
        hs = result.get("human_score")
        if hs:
            score = hs.get("score", 0)
            max_score = hs.get("max", 100)
            verdict = "PASS" if hs.get("is_human", False) else "FAIL"
            print(f"\nHuman Score: {score}/{max_score} [{verdict}]")


def print_usage():
    print("""
Web Agent CLI

Usage:
  python run.py [options] "<prompt>"

Options:
  --model, -m <name>      LLM model (default: env LLM_MODEL or dolphin3)
  --mode, -M <mode>       Execution mode: browser-use (default) or scrapling
  --parallel, -p <n>      Parallel workers (default: 1)
  --area, -a <code>       Country code for proxy (default: env SMARTPROXY_AREA or us)
  --timezone, -t <tz>     Timezone override (default: auto from area)
  --no-proxy              Direct connection (no proxy)
  --verbose, -v           Debug logging

Examples:
  python run.py --no-proxy "Go to https://httpbin.org/ip and get the IP"
  python run.py -a jp "Go to https://httpbin.org/ip and get the IP"
  python run.py -p 3 -a us "Go to https://httpbin.org/ip and get the IP"
  python run.py -m hermes3 --no-proxy "Search google for AI news"

  # Scrapling stealth mode
  python run.py -M scrapling --no-proxy "https://example.com"
  python run.py -M scrapling -a jp "https://httpbin.org/ip"
  SOLVE_CLOUDFLARE=true python run.py -M scrapling "https://target.com"

Environment Variables:
  LLM_PROVIDER            local, openai, anthropic (default: local)
  LLM_BASE_URL            Local LLM server URL (default: http://localhost:11434/v1)
  LLM_MODEL               LLM model name (default: dolphin3)
  LLM_API_KEY             LLM API key (not needed for local)
  SMARTPROXY_USERNAME     SmartProxy ISP username
  SMARTPROXY_PASSWORD     SmartProxy ISP password
  SMARTPROXY_HOST         SmartProxy host (default: isp.decodo.com)
  SMARTPROXY_PORT         SmartProxy port (default: 10001)
  SMARTPROXY_AREA         Default country code (default: us)
  SMARTPROXY_TIMEZONE     Default timezone override
  HEADLESS                Run headless (default: true)
  SOLVE_CLOUDFLARE        Enable Cloudflare bypass in scrapling mode (default: false)
  GOLOGIN_API_TOKEN       GoLogin API token (realistic browser fingerprints, optional)
""")


def main():
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(0)

    opts = parse_args(sys.argv[1:])

    if opts["verbose"]:
        configure_logging(level="DEBUG", json_format=False)

    if opts["mode"] == "scrapling":
        asyncio.run(run_scrapling(opts))
    else:
        asyncio.run(run(opts))


if __name__ == "__main__":
    main()
