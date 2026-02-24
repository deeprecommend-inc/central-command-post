# Execution Test Manual

Manual verification procedures for CCP. Covers setup, unit tests, CLI commands, and integration checks.

Source: `run.py`, `tests/`, `setup.sh`

---

## 0. Prerequisites

```bash
# Setup (first time only)
./setup.sh

# Or manual setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
```

Verify:

```bash
source venv/bin/activate
python3 -c "import playwright; print('playwright OK')"
python3 -c "import browser_use; print('browser-use OK')"
```

---

## 1. Unit Tests (pytest)

All 560 tests. No external dependencies required.

```bash
# Run all tests
python3 -m pytest

# Verbose output
python3 -m pytest -v

# Specific module
python3 -m pytest tests/test_web_agent.py
python3 -m pytest tests/test_browser_worker.py
python3 -m pytest tests/test_proxy_manager.py
python3 -m pytest tests/test_ua_manager.py
python3 -m pytest tests/test_human_score.py
python3 -m pytest tests/test_ccp.py
python3 -m pytest tests/test_integration.py

# By layer
python3 -m pytest tests/test_sense/
python3 -m pytest tests/test_think/
python3 -m pytest tests/test_command/
python3 -m pytest tests/test_control/
python3 -m pytest tests/test_learn/
python3 -m pytest tests/test_security/

# Run with coverage (if installed)
python3 -m pytest --cov=src --cov-report=term-missing

# Run single test
python3 -m pytest tests/test_web_agent.py::TestAgentConfig::test_default_config -v
```

Expected: All 560 tests pass.

---

## 2. CLI Command Tests

### 2.1 Help

```bash
python3 run.py --help
python3 run.py help
```

Expected: Usage text with all commands, options, and environment variables.

### 2.2 URL Navigation (no proxy)

```bash
# Single URL
python3 run.py url --no-proxy https://httpbin.org/ip

# Multiple URLs (parallel)
python3 run.py url --no-proxy https://httpbin.org/ip https://httpbin.org/user-agent https://httpbin.org/headers
```

Expected: Each URL returns success with title and URL.

### 2.3 URL Navigation (with proxy)

Requires: `BRIGHTDATA_USERNAME`, `BRIGHTDATA_PASSWORD` in `.env`

```bash
# Residential IP (default)
python3 run.py url https://httpbin.org/ip

# Mobile IP
python3 run.py url -m https://httpbin.org/ip

# Datacenter IP
python3 run.py url -d https://httpbin.org/ip

# ISP IP
python3 run.py url -i https://httpbin.org/ip
```

Expected: Different IP addresses per proxy type. Proxy stats logged.

### 2.4 Demo

```bash
python3 run.py demo --no-proxy
```

Expected: Navigates to 3 httpbin URLs in parallel. All succeed.

### 2.5 Quick Test

```bash
python3 run.py test --no-proxy
```

Expected: Navigates to `httpbin.org/ip`. Prints IP and title.

### 2.6 Proxy Health Check

Requires: Proxy credentials configured.

```bash
python3 run.py health
python3 run.py health --mobile
```

Expected: Health summary with total/healthy/unhealthy counts, country status, live check results.

Without proxy credentials:

```bash
python3 run.py health --no-proxy
```

Expected: "Proxy Status: Not configured (direct connection mode)"

### 2.7 AI Agent (Cloud LLM)

Requires: `LLM_API_KEY` or `OPENAI_API_KEY` in `.env`

```bash
python3 run.py ai "Go to example.com and get the page title" --no-proxy
```

Expected: Agent navigates, extracts title, prints "Task completed successfully" and human score.

### 2.8 AI Agent (Local LLM)

Requires: Ollama running with a model pulled.

```bash
# Start Ollama (if not running)
ollama serve &
ollama pull dolphin3

# Run with --local flag
python3 run.py ai --local "Go to example.com and get the title" --no-proxy

# Specify model
python3 run.py ai --local --llm-model hermes3 "Search for AI news" --no-proxy

# Specify server URL
python3 run.py ai --llm-base-url http://localhost:11434/v1 --llm-model dolphin3 "Navigate to github.com" --no-proxy
```

Expected: Task executes without API key. Human score printed at end.

### 2.9 Parallel AI Tasks

```bash
python3 run.py parallel --local "Go to example.com" "Go to github.com" "Go to httpbin.org/ip" --no-proxy
```

Expected: All tasks run concurrently (up to PARALLEL_SESSIONS). Summary: "X/3 tasks successful".

### 2.10 Human Score Demo

```bash
python3 run.py score
```

Expected: Synthetic data generates a score report with all metric categories (Time, Engagement, Network, Behavior, Consistency). Score is 0-106.

### 2.11 Notification Channels

```bash
# List channels
python3 run.py channels

# Webhook notification (requires WEBHOOK_URLS in .env)
python3 run.py notify --channel webhook --to "https://httpbin.org/post" "Test message"

# Slack (requires SLACK_WEBHOOK_URL or SLACK_BOT_TOKEN)
python3 run.py notify --channel slack --to "#general" "Alert from CCP"
```

Expected: Channel list shows configured channels. Notifications sent and confirmed.

### 2.12 Vault

```bash
# Initialize vault
python3 run.py vault init

# Store a secret
python3 run.py vault set TEST_KEY test_value

# Retrieve
python3 run.py vault get TEST_KEY

# List keys
python3 run.py vault list

# Delete
python3 run.py vault delete TEST_KEY

# Rotate encryption keys
python3 run.py vault rotate
```

Expected: Each operation succeeds. `get` returns stored value. `delete` removes key. `list` shows remaining keys.

### 2.13 JSON Output

```bash
python3 run.py url --no-proxy --json https://httpbin.org/ip
```

Expected: Structured JSON log output.

### 2.14 Verbose Logging

```bash
python3 run.py url --no-proxy -v https://httpbin.org/ip
```

Expected: DEBUG-level log output.

---

## 3. Proxy Provider Tests

### 3.1 BrightData (default)

```bash
python3 run.py url https://httpbin.org/ip
```

### 3.2 DataImpulse

```bash
python3 run.py url --proxy-provider dataimpulse https://httpbin.org/ip
```

### 3.3 GeoNode

```bash
python3 run.py url --proxy-provider geonode https://httpbin.org/ip
```

### 3.4 Generic Proxy

Set `PROXY_HOST`, `PROXY_PORT`, `PROXY_USERNAME`, `PROXY_PASSWORD` in `.env`.

```bash
python3 run.py url --proxy-provider generic https://httpbin.org/ip
```

Expected: Each provider returns a different IP. Connection established successfully.

---

## 4. Antidetect Browser Test

### 4.1 AdsPower

Requires: AdsPower running locally with a profile configured.

```bash
export ADSPOWER_API_BASE=http://local.adspower.com:50325
export ADSPOWER_PROFILE_ID=<your-profile-id>

python3 run.py ai --adspower "Go to example.com" --no-proxy
```

Expected: Browser opens via AdsPower API using the configured profile fingerprint.

---

## 5. CAPTCHA Solver Tests

### 5.1 Vision Solver (default)

```bash
python3 run.py ai "Go to a site with CAPTCHA and solve it" --no-proxy
```

### 5.2 2captcha

Requires: `TWOCAPTCHA_API_KEY` in `.env`

```bash
python3 run.py ai --captcha-solver 2captcha "Navigate to site with CAPTCHA" --no-proxy
```

### 5.3 Anti-Captcha

Requires: `ANTICAPTCHA_API_KEY` in `.env`

```bash
python3 run.py ai --captcha-solver anti-captcha "Navigate to site with CAPTCHA" --no-proxy
```

Expected: CAPTCHA detected, solved, and page progresses past challenge.

---

## 6. Docker Tests

### 6.1 Build

```bash
docker build -t ccp .
```

Expected: Multi-stage build completes. Image created.

### 6.2 Run Server

```bash
docker run -d -p 8000:8000 --name ccp-test ccp
curl http://localhost:8000/health
docker stop ccp-test && docker rm ccp-test
```

Expected: Health check returns OK.

### 6.3 Docker Compose

```bash
docker compose up -d
curl http://localhost:8000/health
docker compose down
```

Expected: All services start. Health check passes.

---

## 7. Environment Variable Validation

| Test | Command | Expected |
|------|---------|----------|
| No API key, cloud LLM | `python3 run.py ai "test"` | Error: "API key required" |
| No API key, local LLM | `python3 run.py ai --local "test" --no-proxy` | Succeeds (no key needed) |
| No proxy creds, no --no-proxy | `python3 run.py url https://httpbin.org/ip` | Falls back to direct connection |
| Invalid command | `python3 run.py invalid` | "Unknown command" + usage |
| No URL for url command | `python3 run.py url` | "Error: URL required" |
| No task for ai command | `python3 run.py ai` | "Error: Task description required" |

---

## 8. Error Recovery Tests

### 8.1 Proxy Failure Retry

Disconnect proxy mid-session. Agent should retry with exponential backoff (1s -> 2s -> 4s, max 30s) and switch to a different proxy.

### 8.2 LLM Server Down

Stop Ollama, then run:

```bash
python3 run.py ai --local "test" --no-proxy
```

Expected: Connection error. Task fails immediately without hanging.

### 8.3 Invalid URL

```bash
python3 run.py url --no-proxy not-a-url
```

Expected: Validation error. No crash.

---

## 9. Test Checklist

| # | Category | Test | Status |
|---|----------|------|--------|
| 1 | Unit | `pytest` all 560 pass | |
| 2 | CLI | `help` displays usage | |
| 3 | CLI | `url --no-proxy` single URL | |
| 4 | CLI | `url --no-proxy` multiple URLs | |
| 5 | CLI | `demo --no-proxy` | |
| 6 | CLI | `test --no-proxy` | |
| 7 | CLI | `score` human score demo | |
| 8 | CLI | `vault init/set/get/list/delete/rotate` | |
| 9 | CLI | `channels` list | |
| 10 | CLI | `--json` output format | |
| 11 | CLI | `-v` verbose logging | |
| 12 | AI | `ai --local` with Ollama | |
| 13 | AI | `ai --local --llm-model` model selection | |
| 14 | AI | `parallel --local` multiple tasks | |
| 15 | Proxy | Residential IP | |
| 16 | Proxy | Mobile IP | |
| 17 | Proxy | Datacenter IP | |
| 18 | Proxy | Health check | |
| 19 | Proxy | Provider switch (dataimpulse/geonode) | |
| 20 | Error | Missing API key (cloud) | |
| 21 | Error | LLM server down | |
| 22 | Error | Invalid URL | |
| 23 | Error | Invalid command | |
| 24 | Docker | Build succeeds | |
| 25 | Docker | Health check passes | |
