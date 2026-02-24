# Local LLM Setup

Procedure for running CCP's browser-use agent with a local LLM server instead of cloud APIs.

No API key required. All local LLM servers expose an OpenAI-compatible `/v1/chat/completions` endpoint, so `ChatOpenAI` works with just a `base_url` swap.

---

## 1. Install and Start an LLM Server

Choose one:

### Ollama (default)

```bash
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull dolphin3
ollama serve
# Endpoint: http://localhost:11434/v1
```

### LM Studio

```bash
# Start server from GUI
# Endpoint: http://localhost:1234/v1
```

### vLLM

```bash
pip install vllm
vllm serve <model-name>
# Endpoint: http://localhost:8000/v1
```

### llama.cpp

```bash
llama-server -m <model-file>
# Endpoint: http://localhost:8080/v1
```

### LocalAI

```bash
local-ai
# Endpoint: http://localhost:8080/v1
```

---

## 2. Configure Environment

```bash
cp .env.example .env
```

Minimum `.env`:

```env
LLM_PROVIDER=local
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=dolphin3
```

`LLM_API_KEY` is not needed. The code auto-sets `"not-needed"` via `BrowserUseConfig.effective_api_key`.

---

## 3. Run

```bash
# Using .env config
python run.py ai "Go to example.com and get the title" --no-proxy

# Using CLI flags (no .env needed)
python run.py ai --local "Go to example.com and get the title" --no-proxy

# Specify model
python run.py ai --local --llm-model hermes3 "Search for AI news" --no-proxy

# Specify server URL (LM Studio, vLLM, etc.)
python run.py ai --llm-base-url http://localhost:1234/v1 --llm-model dolphin3 "Navigate to github.com" --no-proxy

# Parallel execution
python run.py parallel --local "task 1" "task 2" "task 3" --no-proxy
```

---

## 4. Configuration Priority

CLI flags override environment variables:

| Setting | CLI Flag | Env Var | Default (when --local) |
|---------|----------|---------|------------------------|
| Provider | `--local` | `LLM_PROVIDER` | `openai` -> `local` |
| Server URL | `--llm-base-url` | `LLM_BASE_URL` | `http://localhost:11434/v1` |
| Model | `--llm-model` | `LLM_MODEL` | `dolphin3` |

`--local` flag sets `llm_provider=local` and applies defaults for unset base_url and model (`run.py:61-66`).

---

## 5. Internal Flow

```
CLI (--local)
  -> run.py: set llm_provider="local"
  -> run_ai_agent(): skip API key check (provider == "local")
  -> BrowserUseConfig.effective_api_key -> "not-needed"
  -> BrowserUseAgent._create_llm():
       ChatOpenAI(model=model, api_key="not-needed", base_url=base_url)
  -> browser-use Agent executes task via local LLM
```

Source: `src/browser_use_agent.py:292-302`

---

## 6. Recommended Models

| Model | Use Case | Notes |
|-------|----------|-------|
| `dolphin3` | General purpose, uncensored | Default |
| `hermes3` | Reasoning, tool use | Function calling support |
| `llama3.1` | General purpose | Meta official |
| `wizardlm2` | Code, reasoning | - |
| `mythomax` | Creative tasks | - |

---

## 7. Notes

- CAPTCHA solving requires a vision-capable model if using local LLM for vision (`src/browser_use_agent.py:366-375`)
- Without `--no-proxy`, BrightData connection is attempted first (falls back to direct if unconfigured)
- If the local LLM server is not running, the task fails immediately with a connection error
- The `--local` flag is shorthand; alternatively set `LLM_PROVIDER=local` in `.env` for persistent config
