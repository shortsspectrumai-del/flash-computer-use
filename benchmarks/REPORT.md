# Speed & Accuracy Benchmark Report

Hardware environment used for baseline measurements: **LiquidAI D1 3B (Q8_0)** running on **Ollama 0.40.4**, **NVIDIA GTX 1050 (4 GB VRAM)** (~2.5 GB model footprint in VRAM).

---

## 1. Synthetic Dense E-Commerce Page Benchmark

The benchmark (`benchmarks/browser_speed.py`) evaluates page readiness detection (`wait_until_ready`) followed by locating, filling, verifying, and submitting a search input (`smart_type`) on a dense synthetic store page containing 50+ interactive elements.

| Metric | Baseline (Vision-Only, Unoptimized) | Optimized Vision-Only (`D1_BROWSER_STRATEGY=vision`) | Hybrid Mode (`D1_BROWSER_STRATEGY=hybrid`, Default) |
|---|---:|---:|---:|
| **Readiness Check (`wait_until_ready`)** | `24.247 s` (D1 1280×800) | `4.068 s` (D1 768×480) | **`0.002 – 0.007 s`** (`2–7 ms`, DOM) |
| **Search Fill + Verification + Submit (`smart_type`)** | `26.795 s` (Failed / Low confidence) | `2.556 s` (D1 cropped 646×115, Verified) | **`0.177 – 0.251 s`** (`177–251 ms`, Verified) |
| **Total End-to-End Tool Time** | `51.042 s` (Failed) | `6.624 s` (100% Pass) | **`~0.18 – 0.26 s`** (**100% Pass**) |
| **D1 Vision Inference Calls** | 2 | 2 | **0** |
| **Exact Input Value & Submission Verified** | No (`0/1`) | Yes (`1/1`) | **Yes (`3/3`)** |

### Why Hybrid + Cropped Vision Is Up to 200× Faster

1. **Instant DOM & Accessibility Short-Circuit (`hybrid`)**:
   - When an element has a unique accessible label or unique `searchbox` role, `smart_click`, `smart_move`, and `smart_type` resolve the target deterministically in **2–7 ms** without screenshot encoding or VLM inference.
   - Multi-point unoccluded hit-testing (`elementFromPoint` across 9 interior points) ensures the click lands on an exposed pixel even when badges or icons overlap the element's geometric center.
2. **Targeted Candidate Cropping & Bilinear Downscaling (`vision` fallback)**:
   - When visual disambiguation is needed, full-screen images are downscaled to `D1_IMAGE_MAX_SIDE=768` (reducing visual tokens by ~64%) and `smart_type` crops tightly around candidate input fields (`646×115`), cutting D1 inference latency on a 4 GB GPU from **26.8 s → 2.5 s** while boosting confidence from `0.40` (failed) to `0.91` (verified).
3. **Zero-Pause Human-Like Pointer Trajectory**:
   - `pyautogui.PAUSE`, `MINIMUM_DURATION`, and `MINIMUM_SLEEP` are zeroed out (`_fast_pyautogui()`), replacing sluggish 100 ms per-step sleeps with a high-frequency minimum-jerk trajectory ($10t^3 - 15t^4 + 6t^5$) that completes in ~`40 ms`.

---

## 2. Live Web & WAF Detection Benchmark

In live tests (`benchmarks/amazon_search.py`):
- When the search bar label differs from the generic query, the automatic D1 visual fallback locates and submits the search in **`3.979 s`** (`benchmarks/amazon-after-vision.json`) with `typed_verified=true`.
- When an upstream anti-bot challenge (HTTP 202 `x-amzn-waf-action` or captcha interstitial) is served, `browser_open` detects it immediately in **`1.326 s`** (`benchmarks/amazon-after.json`) and returns `status="blocked"`, `block_reason="waf_challenge"` without wasting 30+ seconds on futile VLM retries.

---

## 3. Reproducing the Benchmarks

```bash
# Hybrid mode (default, 3 runs)
D1_BENCH_RUNS=3 .venv/bin/python benchmarks/browser_speed.py benchmarks/after.json

# Forced D1 Vision mode
D1_BROWSER_STRATEGY=vision D1_BENCH_RUNS=1 .venv/bin/python benchmarks/browser_speed.py benchmarks/after-vision.json

# Desktop hierarchical grid precision benchmark
.venv/bin/python benchmarks/desktop_precision.py

# Full automated test suite (68 tests)
.venv/bin/python -m pytest -q
```
