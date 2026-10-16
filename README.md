# ⚡ Flash computer use — Ultra-Fast Hybrid Browser & Desktop MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![MCP Compatible](https://img.shields.io/badge/MCP-Model%20Context%20Protocol-green.svg)](https://modelcontextprotocol.io/)
[![OS: Linux | Windows | macOS](https://img.shields.io/badge/OS-Linux%20%7C%20Windows%20%7C%20macOS-informational.svg)](#8-cross-platform-support-linux-windows-macos)
[![Tests: 68 Passed](https://img.shields.io/badge/Tests-68%20passed-brightgreen.svg)](#9-speed--accuracy-benchmarks)

**Flash computer use** is a high-speed, precision-engineered **Model Context Protocol (MCP)** server in Python for controlling both **web browsers** (Playwright) and the **physical OS desktop** (Linux X11, Windows, macOS).

Unlike traditional screenshot-only computer-use agents that take 20–50 seconds per action and generate hallucinated `[x, y]` coordinates, **Flash computer use** combines **instant deterministic DOM & native OS accessibility targeting (`2–7 ms`)** with **calibrated Set-of-Mark / hierarchical grid visual decision fallback (`LiquidAI D1`)**—while always moving the **real physical OS mouse pointer** along a smooth, human-like minimum-jerk trajectory.

---

## ✨ Key Highlights

- 🚀 **Up to 200× Faster Hybrid Execution (`hybrid` mode)**:
  - **Browser**: Instantly resolves unique accessible labels and `searchbox` roles via DOM inspection in **2–7 ms** and verifies unoccluded click points (`elementFromPoint` multi-point hit-testing), falling back to D1 vision only when targets are ambiguous.
  - **Desktop**: Queries native OS accessibility trees (**Linux AT-SPI**, **Windows UI Automation**, **macOS AXUIElement**) with automatic cache invalidation, bypassing screenshot capture and VLM inference whenever an exact accessible control exists.
- 🖱️ **Human-Like Physical OS Mouse Movement (Web + Desktop)**:
  - Always moves the real physical OS cursor along a **minimum-jerk trajectory** ($10t^3 - 15t^4 + 6t^5$) with a subtle natural wrist arc and exact pixel landing.
  - In visible browser mode, automatically maps Playwright viewport coordinates to global screen coordinates before every click, typing action, scroll, drag, or popup action.
- 🎨 **Paint & `<canvas>` Drawing + Dragging**:
  - Automatically detects the largest white/light drawing sheet (`canvas_bounds`) in desktop paint apps (**MS Paint**, **KolourPaint**, **Pinta**, etc.) or HTML5 `<canvas>` elements in the browser.
  - Supports smooth direct dragging (`mouse_drag`), continuous freehand & multi-stroke paths with anti-gap interpolation (`draw_path`), and 12 ready-to-use geometric shapes (`draw_shape`).
- 🛡️ **Zero Coordinate Hallucination**:
  - Uses **LiquidAI D1** via native `/v1/systemone` decision probabilities (`noul`, `choice`, `score` with zero generated tokens) over Set-of-Mark badges and coarse-to-fine grids (**Ollama**, **local Hugging Face Transformers**, or **Cloud API**).
- 💻 **Cross-Platform Precision**:
  - Built-in **Windows Per-Monitor DPI Awareness**, **macOS Retina multi-monitor scaling**, and **Linux X11** native clipboard & pointer integration.

---

## 📖 Table of Contents

1. [Speed & Accuracy Benchmarks](#1-speed--accuracy-benchmarks)
2. [System Requirements](#2-system-requirements)
3. [Step-by-Step Installation](#3-step-by-step-installation)
4. [Ollama & D1 Model Setup](#4-ollama--d1-model-setup)
5. [MCP Client Configuration (Cursor, Claude, Codex, Antigravity)](#5-mcp-client-configuration-cursor-claude-codex-antigravity)
6. [Environment Variables Reference](#6-environment-variables-reference)
7. [Complete Reference of All 15 MCP Tools](#7-complete-reference-of-all-15-mcp-tools)
8. [Drawing in Paint, KolourPaint & Web Canvas](#8-drawing-in-paint-kolourpaint--web-canvas)
9. [Cross-Platform Support (Linux, Windows, macOS)](#9-cross-platform-support-linux-windows-macos)

---

## 1. Speed & Accuracy Benchmarks

Measured on a dense synthetic e-commerce page (50+ interactive elements) using **LiquidAI D1 3B (Q8_0)** on **Ollama 0.40.4** (NVIDIA GTX 1050 4 GB VRAM). Full details and raw JSON outputs are in [`benchmarks/REPORT.md`](benchmarks/REPORT.md).

| Benchmark Step | Baseline (Unoptimized Vision) | Optimized Vision (`D1_BROWSER_STRATEGY=vision`) | Hybrid Mode (`D1_BROWSER_STRATEGY=hybrid`, Default) |
|---|---:|---:|---:|
| **Readiness Check (`wait_until_ready`)** | `24.247 s` (1280×800 D1) | `4.068 s` (768×480 D1) | **`0.002 – 0.007 s`** (`2–7 ms`, DOM) |
| **Search Fill + Verify + Submit (`smart_type`)** | `26.795 s` (Failed, low confidence) | `2.556 s` (646×115 cropped D1, Verified) | **`0.177 – 0.251 s`** (`177–251 ms`, Verified) |
| **Total End-to-End Tool Execution** | `51.042 s` (Failed) | `6.624 s` (100% Pass) | **`~0.18 – 0.26 s`** (**100% Pass**) |
| **VLM Inference Calls** | 2 | 2 | **0** |
| **Exact Input Value & Submit Verified** | No (`0/1`) | Yes (`1/1`) | **Yes (`3/3`)** |

### Why It Is So Fast
1. **Deterministic DOM & Native Accessibility First (`hybrid`)**: Unique accessible labels and roles bypass VLM calls entirely (`2–7 ms`).
2. **Candidate Region Cropping & Downscaling (`vision`)**: When D1 vision fallback is triggered, images are proportionally downscaled (`D1_IMAGE_MAX_SIDE=768`) and input candidates are tightly cropped (`646×115`), cutting GPU latency by **10×** (`26.8 s → 2.55 s`) and increasing model confidence from `0.40` to `0.91`.
3. **Zero-Lag OS Pointer**: Removes PyAutoGUI's default `100 ms` per-step sleep, executing smooth minimum-jerk human curves in ~`40 ms`.

Reproduce the benchmarks locally:

```bash
# Hybrid mode benchmark (3 runs)
D1_BENCH_RUNS=3 .venv/bin/python benchmarks/browser_speed.py benchmarks/after.json

# Forced D1 Vision fallback benchmark
D1_BROWSER_STRATEGY=vision D1_BENCH_RUNS=1 .venv/bin/python benchmarks/browser_speed.py benchmarks/after-vision.json

# Desktop hierarchical grid precision benchmark
.venv/bin/python benchmarks/desktop_precision.py
```

---

## 2. System Requirements

- **Python**: `>= 3.11`
- **Package Manager**: [`uv`](https://docs.astral.sh/uv/) (recommended) or `pip`
- **Decision Engine Provider (choose one)**:
  - **Ollama** (recommended, local): version supporting `/v1/systemone` (e.g. `>= 0.40`) with `d1:3b`
  - **Local Transformers**: CUDA / Apple MPS / CPU with `LiquidAI/d1-3B`
  - **Cloud API**: any endpoint implementing `/v1/systemone`
- **OS Desktop Prerequisites**:
  - **Linux**: active **X11** session (`DISPLAY`) and `xclip` or `xsel` for fast Unicode clipboard pasting.
  - **Windows**: interactive desktop session (Per-Monitor DPI Awareness is enabled automatically).
  - **macOS**: grant **Accessibility** and **Screen Recording** permissions to your terminal / MCP client.

---

## 3. Step-by-Step Installation

### Linux / macOS

```bash
git clone https://github.com/shortsspectrumai-del/flash-computer-use.git
cd flash-computer-use

# 1. Create virtual environment and install dependencies
uv venv
uv pip install -e '.[dev]'

# 2. Install Playwright Chromium
PLAYWRIGHT_BROWSERS_PATH=.runtime/playwright .venv/bin/python -m playwright install chromium
```

### Windows (PowerShell)

```powershell
git clone https://github.com/shortsspectrumai-del/flash-computer-use.git
cd flash-computer-use

uv venv
uv pip install -e ".[dev,accessibility]"
$env:PLAYWRIGHT_BROWSERS_PATH=".runtime\playwright"
.\.venv\Scripts\python.exe -m playwright install chromium
```

---

## 4. Ollama & D1 Model Setup

Pull the `d1:3b` decision model and verify your environment:

```bash
# Pull LiquidAI D1 3B model
ollama pull d1:3b

# Check OS desktop capabilities, accessibility backend, and Python dependencies
.venv/bin/flash-doctor

# Verify D1 decision inference (binary noul, choice, score) on a synthetic image
D1_PROVIDER=ollama D1_MODEL_NAME=d1:3b .venv/bin/flash-check --inference
```

---

## 5. MCP Client Configuration (Cursor, Claude, Codex, Antigravity)

### Auto-Generate Portable MCP JSON

Generate a ready-to-use JSON configuration pointing to your current Python environment:

```bash
.venv/bin/flash-config --ollama-url http://localhost:11434
```

Save directly to a file:

```bash
.venv/bin/flash-config --ollama-url http://localhost:11434 --output mcp.json
```

---

### A. Cursor / Claude Desktop / Google Antigravity (`mcp.json` / `claude_desktop_config.json`)

Add the following block to your client's MCP configuration file (see [`examples/mcp.ollama.json`](examples/mcp.ollama.json)):

```json
{
  "mcpServers": {
    "Flash computer use": {
      "command": "/absolute/path/to/flash-computer-use/run-mcp.sh",
      "env": {
        "D1_PROVIDER": "ollama",
        "D1_MODEL_NAME": "d1:3b",
        "D1_OLLAMA_BASE_URL": "http://localhost:11434",
        "D1_TIMEOUT_SECONDS": "120",
        "D1_BROWSER_STRATEGY": "hybrid",
        "D1_DESKTOP_STRATEGY": "hybrid",
        "D1_IMAGE_MAX_SIDE": "768",
        "D1_REAL_MOUSE": "true",
        "D1_MOUSE_DURATION": "0.04"
      }
    }
  }
}
```

*(On **Windows**, set `"command"` to `"C:\\absolute\\path\\to\\flash-computer-use\\run-mcp.cmd"`).*

---

### B. OpenAI Codex CLI (`~/.codex/config.toml`)

Register via CLI:

```bash
codex mcp add "Flash computer use" \
  --env D1_PROVIDER=ollama \
  --env D1_MODEL_NAME=d1:3b \
  --env D1_OLLAMA_BASE_URL=http://localhost:11434 \
  --env D1_TIMEOUT_SECONDS=120 \
  --env D1_BROWSER_STRATEGY=hybrid \
  --env D1_DESKTOP_STRATEGY=hybrid \
  -- '/absolute/path/to/flash-computer-use/run-mcp.sh'
```

Or copy [`examples/codex.ollama.toml`](examples/codex.ollama.toml) into `~/.codex/config.toml`:

```toml
[mcp_servers."Flash computer use"]
command = "/absolute/path/to/flash-computer-use/run-mcp.sh"
startup_timeout_sec = 30
tool_timeout_sec = 120

[mcp_servers."Flash computer use".env]
D1_PROVIDER = "ollama"
D1_MODEL_NAME = "d1:3b"
D1_OLLAMA_BASE_URL = "http://localhost:11434"
D1_TIMEOUT_SECONDS = "120"
D1_BROWSER_STRATEGY = "hybrid"
D1_DESKTOP_STRATEGY = "hybrid"
D1_IMAGE_MAX_SIDE = "768"
```

---

### C. Claude Code CLI

```bash
claude mcp add --transport stdio \
  --env D1_PROVIDER=ollama \
  --env D1_MODEL_NAME=d1:3b \
  --env D1_OLLAMA_BASE_URL=http://localhost:11434 \
  "Flash computer use" -- '/absolute/path/to/flash-computer-use/run-mcp.sh'
```

---

## 6. Environment Variables Reference

See [`.env.example`](.env.example) for a complete template.

| Variable | Default | Description |
|---|---|---|
| `D1_PROVIDER` | `local` | Decision provider: `ollama`, `local` (Transformers), or `api` |
| `D1_MODEL_NAME` | `d1:3b` / `LiquidAI/d1-3B` | Model identifier for Ollama (`d1:3b`) or Hugging Face / API |
| `D1_OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server base URL |
| `D1_OLLAMA_KEEP_ALIVE` | `10m` | Keeps the model warm in memory between tool calls |
| `D1_API_BASE_URL` | — | Base URL for `/v1/systemone` when `D1_PROVIDER=api` |
| `D1_API_KEY` | — | Bearer API key when `D1_PROVIDER=api` |
| `D1_TIMEOUT_SECONDS` | `60` | Provider HTTP timeout in seconds |
| `D1_BROWSER_STRATEGY` | `hybrid` | `hybrid` (fast DOM + D1 fallback) or `vision` (always D1) |
| `D1_DESKTOP_STRATEGY` | `hybrid` | `hybrid` (native OS accessibility + D1 fallback) or `vision` |
| `D1_IMAGE_MAX_SIDE` | `768` | Max image dimension sent to D1 (`0` disables downscaling) |
| `D1_CONFIDENCE_THRESHOLD` | `0.65` | Minimum confidence required to authorize a click |
| `D1_BROWSER_HEADLESS` | `false` | `false` for visible browser window, `true` for headless |
| `D1_BROWSER_CDP_URL` | — | Optional CDP endpoint (e.g. `http://localhost:9222`) to attach to an existing browser |
| `D1_BROWSER_PAGE_URL` | — | Exact tab URL to select when CDP exposes multiple tabs |
| `D1_MONITOR` | `1` | MSS monitor index for desktop screen capture |
| `D1_REAL_MOUSE` | `true` | Always move the real physical OS mouse cursor during visible browser actions (`false` to disable, `always` to force even in headless) |
| `D1_MOUSE_DURATION` | `0.04` | Default duration (in seconds) of the human-like minimum-jerk pointer trajectory |

---

## 7. Complete Reference of All 15 MCP Tools

Every tool call is serialized via an async lock and returns compact structured JSON including execution time (`elapsed_ms`).

### Browser & Popup Navigation
1. **`browser_open(url)`**: Opens a URL and returns page title, `ready` status, accessible input field labels, short text preview, and any detected popup/cookie banner details.
2. **`handle_popup(action="inspect" | "reject" | "accept" | "dismiss", max_scrolls=8)`**: Inspects or resolves cookie banners, modal dialogs, and Google/YouTube consent pages (automatically scrolling terms if the action button is disabled until the bottom).
3. **`browser_scroll(direction="down" | "up", pixels=600, container="auto" | "popup" | "page")`**: Scrolls the active popup container or the main page.

### Smart Hybrid Actions (`mode="browser"` or `mode="desktop"`)
4. **`smart_click(target_description, mode="browser", double_click=False)`**: Locates the target via DOM/accessibility or Set-of-Mark / hierarchical D1 grid, moves the real physical pointer along a human curve, and clicks an unoccluded point.
5. **`smart_move(target_description, mode="desktop")`**: Locates the target and moves the mouse pointer onto it without clicking (hover).
6. **`smart_type(target_description, text_to_type, press_enter=True, mode="browser")`**: Filters editable fields, replaces existing text, verifies the exact typed value (`typed_verified=true`), and optionally presses Enter.
7. **`scroll_until_visible(target_description, direction="down", max_scrolls=8, mode="browser")`**: Scrolls step-by-step until $P(\text{visible}) \ge 0.80$.
8. **`visual_assert(questions, mode="browser")`**: Evaluates 1–64 binary visual questions in a single D1 call. Probabilities between `0.20` and `0.80` return `answer=null, certain=false`.
9. **`wait_until_ready(timeout_seconds=10, mode="browser")`**: Fast DOM readiness check in `hybrid` mode or visual polling $P(\text{ready}) \ge 0.80$ in `vision`/`desktop` mode.
10. **`desktop_inspect()`**: Returns OS portability status, visible native accessibility elements, and auto-detected drawing sheet bounds (`canvas_bounds`).

### Direct Mouse Control & Paint / Canvas Drawing
11. **`mouse_move(x, y, duration=0.04, mode="desktop")`**: Moves the pointer to `(x, y)` along a minimum-jerk human curve without clicking.
12. **`mouse_click(x=None, y=None, button="left", double_click=False, mode="desktop")`**: Clicks (`left`, `right`, `middle`) at the current cursor position or after moving to `(x, y)`.
13. **`mouse_drag(start_x, start_y, end_x, end_y, button="left", duration=0.12, mode="desktop")`**: Moves to `(start_x, start_y)`, presses the mouse button, drags smoothly along an interpolated path to `(end_x, end_y)`, and safely releases.
14. **`draw_path(points, canvas_bounds=None, duration=0.4, mode="desktop")`**: Draws by dragging the mouse across the canvas sheet. Supports both a single polyline `[[x, y], ...]` and **multi-stroke drawings** `[[[x, y], ...], ...]` (lifting the mouse button between strokes). When `canvas_bounds` is omitted, automatically detects the active Paint sheet or `<canvas>`.
15. **`draw_shape(shape, x=None, y=None, width=None, height=None, canvas_bounds=None, duration=0.4, mode="desktop")`**: Draws a geometric shape (`line`, `rectangle`, `ellipse`, `circle`, `triangle`, `diamond`, `star`, `arrow`, `heart`, `house`, `spiral`, `wave`). Automatically detects the canvas and centers the shape when bounds or coordinates are omitted.

---

## 8. Drawing in Paint, KolourPaint & Web Canvas

**Flash computer use** can control raster and vector drawing applications just like a human user:

- **Automatic Drawing Sheet Detection (`canvas_bounds`)**: You do not need to manually measure the canvas coordinates. The server inspects accessibility roles (`canvas`, `drawing area`) and falls back to a fast largest-rectangle histogram detector (`detect_canvas_from_image`) that locates the white/light drawing sheet inside Paint, KolourPaint, Pinta, or browser `<canvas>` apps.
- **Anti-Gap Stroke Interpolation**: Fast mouse drags in Paint often leave dotted gaps if points are far apart. `interpolate_stroke` subdivides long segments into dense ~`6–8 px` steps while preserving exact sharp corners.
- **12 Built-In Shapes (`draw_shape`)**: `line`, `rectangle`, `ellipse`, `circle`, `triangle`, `diamond`, `star`, `arrow`, `heart`, `house`, `spiral`, `wave`.
- **Guaranteed `mouseUp` Safety**: Every drag and drawing operation wraps pointer state in a `try ... finally` block so the mouse button is never left held down on error.

---

## 9. Cross-Platform Support (Linux, Windows, macOS)

| Operating System | Native Accessibility Backend | Coordinate & DPI Scaling | Unicode Text Input |
|---|---|---|---|
| **Linux (X11)** | AT-SPI (`gi.repository.Atspi`) | Direct X11 screen coordinates | `xclip` / `xsel` clipboard + `Ctrl+V` or `pyautogui.write` fallback |
| **Windows** | UI Automation (`pywinauto` / PowerShell UIA) | Automatic Per-Monitor DPI Awareness (`shcore` / `user32`) | `Set-Clipboard` + `Ctrl+V` or `pyautogui.write` fallback |
| **macOS** | Accessibility API (`ApplicationServices` / `osascript`) | Automatic Retina physical-to-logical scaling (`mss` ↔ `pyautogui`) | `pbcopy` + `Cmd+V` or `pyautogui.write` fallback |

---

## 🧪 Running the Test Suite

Run all 68 automated unit and integration tests (covering MCP stdio protocol, D1 HTTP contract, DOM & accessibility targeting, popup handling, human mouse trajectories, and real HTML5 `<canvas>` drawing):

```bash
.venv/bin/python -m pytest -q
```

---

## 📄 License

Released under the [MIT License](LICENSE).
