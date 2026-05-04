# Manimator

A desktop app that turns natural language prompts into [ManimGL](https://github.com/3b1b/manim) animations — like 3Blue1Brown videos, generated on demand.

Type a prompt like *"visualize the two sum algorithm"* and the app:
1. Sends it to an LLM (local or cloud)
2. Generates ManimGL Python code
3. Renders it to MP4
4. Plays it in-app with save/export options

If the render fails, the app automatically asks the LLM to fix the error and retries up to 3 times.

---

## Screenshots

```
┌─────────────────────────┬──────────────────────────────────────┐
│  Chat                   │  [Video]  [Code]                     │
│                         │                                      │
│  You: visualize         │  ┌──────────────────────────────┐   │
│  binary search          │  │                              │   │
│                         │  │      Animation plays here    │   │
│  ●  Generating…         │  │                              │   │
│                         │  └──────────────────────────────┘   │
│  ⟳ Auto-fixing          │  ▶  ━━━━━━━━━━━━━  0:12 / 0:24  ⬇  │
│     attempt 1/3         │                                      │
├─────────────────────────┴──────────────────────────────────────┤
│  Context: 1,200 / 8,192 tokens  │  Rendering frame 42/120     │
└────────────────────────────────────────────────────────────────┘
```

---

## Requirements

- **macOS** (tested on macOS 14+; Linux should work with minor changes)
- **Python 3.10+** — manimgl 1.7.x requires Python 3.10 or newer
- **ffmpeg** — for video re-encoding and GIF export
- An LLM backend (see [Backends](#backends))

---

## Installation

### 1. Install system dependencies

```bash
brew install python@3.14 ffmpeg
```

### 2. Clone and set up the project

```bash
git clone https://github.com/yourname/manimator
cd manimator

# Create a virtual environment with Python 3.10+
/opt/homebrew/bin/python3.14 -m venv venv
source venv/bin/activate

# Python 3.13+ shims (audioop and pkg_resources were removed from stdlib)
pip install "setuptools<75" audioop-lts

# Install dependencies
pip install -r requirements.txt

# Pin pyglet — manimgl requires pyglet < 2.0
pip install "pyglet==1.5.31"
```

### 3. Run the app

```bash
source venv/bin/activate
python main.py
```

> **Note:** Always run from a foreground terminal window. PyQt6 requires a display and will fail if launched as a background process.

---

## Backends

Manimator works with any OpenAI-compatible API. Choose the backend that suits you.

### Option A — LM Studio (local, recommended for privacy)

1. Download [LM Studio](https://lmstudio.ai)
2. Download a model — **Qwen2.5-Coder-7B-Instruct** or larger works well
3. Click **Start Server** in LM Studio (runs on `http://localhost:1234`)
4. In Manimator → **⚙ Settings** → Backend: **LM Studio**

No API key needed. No rate limits. Runs entirely on your machine.

### Option B — OpenRouter (cloud, easy to start)

1. Create a free account at [openrouter.ai](https://openrouter.ai)
2. Get your API key from [openrouter.ai/keys](https://openrouter.ai/keys)
3. In Manimator → **⚙ Settings** → Backend: **OpenRouter** → paste your key
4. Select a model (see [Recommended Models](#recommended-models))

> **Free tier limits:** 50 requests/day shared across all free models. Add $5 credits to unlock 1,000 requests/day.

### Option C — Ollama (local)

```bash
brew install ollama
ollama serve
ollama pull qwen2.5-coder:7b
```

In Manimator → **⚙ Settings** → Backend: **Ollama**

### Option D — Custom OpenAI-compatible server

Set a custom base URL in **⚙ Settings** → Backend: **Custom URL**.

---

## Recommended Models

| Backend | Model | Notes |
|---|---|---|
| LM Studio | `Qwen2.5-Coder-7B-Instruct` | Good balance of speed and quality |
| LM Studio | `Qwen2.5-Coder-32B-Instruct` | Best local quality, needs ~20 GB RAM |
| OpenRouter (free) | `openai/gpt-oss-20b:free` | Currently working free model |
| OpenRouter (free) | `openai/gpt-oss-120b:free` | Larger, better quality |
| OpenRouter (paid) | `anthropic/claude-sonnet-4-5` | Best overall quality |
| OpenRouter (paid) | `openai/gpt-4o-mini` | Fast and cheap |
| Ollama | `qwen2.5-coder:7b` | Good local option |

---

## Usage

### Basic prompt

Type a prompt in the input box and press **Enter** (or **Shift+Enter** for a new line):

```
visualize the two sum algorithm
animate bubble sort step by step
show how a binary search tree works
explain dijkstra's shortest path
```

### Follow-up / edit

After an animation renders, type a follow-up to modify it:

```
make the arrows red
add labels showing the time complexity
speed up the animation
```

### Controls

| Action | How |
|---|---|
| Send prompt | `Enter` |
| New line in prompt | `Shift+Enter` |
| Re-render last code | **Render Again** button |
| Save as MP4 | **⬇ Save** → choose MP4 |
| Export as GIF | **⬇ Save** → choose GIF |
| View generated code | Click **Code** tab |
| New conversation | **＋ New Chat** toolbar button |
| Change backend/model | **⚙ Settings** toolbar button |

### Self-healing retries

When a render fails, Manimator automatically:
1. Shows a blue **⟳ Auto-fixing — attempt N/3** bubble
2. Sends the error and broken code back to the LLM
3. Asks it to fix and re-render (up to 3 attempts)
4. Records the mistake permanently so the LLM never repeats it

---

## Running Tests

```bash
source venv/bin/activate

# Test code extraction, validator, and a live render (no Qt required)
python test_render.py

# Test OpenRouter API connectivity
OPENROUTER_API_KEY=sk-or-... python test_openrouter.py

# Find which free OpenRouter models are currently working
OPENROUTER_API_KEY=sk-or-... python test_openrouter_flow.py --scan

# Test the full pipeline end-to-end with a specific model
OPENROUTER_API_KEY=sk-or-... python test_openrouter_flow.py --model openai/gpt-oss-20b:free
```

---

## Settings

Open **⚙ Settings** from the toolbar to configure:

| Setting | Description |
|---|---|
| Backend | LM Studio / Ollama / OpenRouter / Hugging Face / Custom |
| API Key | Required for OpenRouter and Hugging Face |
| Model | Type to search — full model list loads from the server |
| Video Quality | Low (480p) / Medium (720p) / High (1080p) |
| Render Timeout | Seconds before giving up on a render (default: 180s) |

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `No LLM detected` banner | Start your backend (Ollama: `ollama serve`, LM Studio: click Start Server) |
| `manimgl not found` | Activate the venv: `source venv/bin/activate` |
| Render hangs indefinitely | Increase timeout in Settings or simplify the prompt |
| `Rate limit exceeded` (OpenRouter) | Wait for daily reset, or add credits at openrouter.ai |
| `502 Provider error` | The selected model doesn't support chat — pick a different one |
| `No code block returned` | The model didn't follow instructions — try a larger/better model |
| GIF export fails | Install ffmpeg: `brew install ffmpeg` |
| App crashes on launch (Python 3.13+) | Run `pip install audioop-lts "setuptools<75"` |

### View logs

```bash
tail -f /tmp/manimator.log
```

---

## Project Structure

```
manimator/
├── main.py                    # Entry point
├── requirements.txt
├── README.md
├── CLAUDE.md                  # Developer guide
├── test_render.py             # Headless render pipeline tests
├── test_openrouter.py         # OpenRouter connectivity test
├── test_openrouter_flow.py    # Full pipeline test against OpenRouter
└── app/
    ├── main_window.py         # Main window, retry loop, signal wiring
    ├── settings.py            # Persistent settings (QSettings)
    ├── core/
    │   ├── llm_client.py      # OpenAI client factory + health check
    │   ├── code_extractor.py  # 4-strategy code extraction from LLM output
    │   ├── code_validator.py  # AST safety scanner
    │   ├── render_pipeline.py # Writes scene file, runs manimgl, parses output
    │   ├── tool_calling.py    # Tool definition + chunk accumulator
    │   ├── conversation.py    # SQLite conversation history
    │   └── mistake_memory.py  # Persistent LLM mistake learning
    ├── workers/
    │   ├── llm_worker.py      # QThread: streams LLM responses
    │   └── render_worker.py   # QThread: runs manimgl subprocess
    ├── ui/
    │   ├── chat_panel.py      # Chat bubbles, prompt input, retry bubble
    │   ├── video_panel.py     # Video player, code view, save/export
    │   ├── settings_dialog.py # Settings UI with live model search
    │   └── status_bar.py      # Context usage + render progress
    └── prompts/
        └── system_prompt.py   # ManimGL API reference injected into every request
```

---

## License

MIT
