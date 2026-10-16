"""Stdio MCP entry point. All tool output is compact structured data."""
import asyncio
import time
from contextlib import asynccontextmanager
from functools import wraps
from typing import Literal, Any

from mcp.server.fastmcp import FastMCP
from .actions import ComputerUse
from .backends import Browser, Desktop
from .d1_engine import D1Engine
from .drawing import shape_points
from .portability import platform_info

_runtime = None
_ui_lock = asyncio.Lock()


@asynccontextmanager
async def lifespan(server):
    global _runtime
    engine, browser = D1Engine(), Browser()
    _runtime = ComputerUse(engine,browser,Desktop())
    try:
        yield _runtime
    finally:
        await browser.close()
        await engine.close()
        _runtime = None


mcp = FastMCP('Flash computer use', lifespan=lifespan)


def guarded(fn):
    @wraps(fn)
    async def call(*args,**kwargs):
        async with _ui_lock:
            started=time.perf_counter()
            try:
                if _runtime is None:
                    raise RuntimeError('MCP runtime is not initialized')
                result=await fn(*args,**kwargs)
                result['elapsed_ms']=round((time.perf_counter()-started)*1000)
                return result
            except Exception as exc:
                # Do not echo provider payloads, screenshots, secrets or typed text.
                from .d1_engine import DecisionError
                detail = str(exc) if isinstance(exc,(DecisionError,ValueError)) else type(exc).__name__
                return {'status':'error','error':detail}
    return call


@mcp.tool()
@guarded
async def browser_open(url: str) -> dict[str, Any]:
    """Open a URL; returns title, readiness, input labels and a short page preview. Returns popup details when one is present: inspect/resolve it with handle_popup using the user's requested choice. If ready is true, skip wait_until_ready. Use the returned field label in smart_type; a preview may reveal an interstitial instead of the requested page."""
    return await _runtime.browser.open(url)


@mcp.tool()
@guarded
async def smart_click(target_description: str, mode: Literal['browser','desktop']='browser', double_click: bool=False) -> dict[str, Any]:
    """Click a uniquely named visible DOM target immediately; otherwise use D1 vision. Duplicate names are ambiguous. Reports method and UI change."""
    return await _runtime.smart_click(target_description,mode,double_click)


@mcp.tool()
@guarded
async def smart_type(target_description: str, text_to_type: str, press_enter: bool=True, mode: Literal['browser','desktop']='browser') -> dict[str, Any]:
    """Fill a visible editable input, replacing old text; verify its exact value before optional Enter. Quote its accessible label from browser_open for a fast precise match. Check status and typed_verified before claiming success."""
    return await _runtime.smart_type(target_description,text_to_type,press_enter,mode)


@mcp.tool()
@guarded
async def scroll_until_visible(target_description: str, direction: Literal['down','up']='down', max_scrolls: int=8, mode: Literal['browser','desktop']='browser') -> dict[str, Any]:
    """Scroll in steps until visual P(visible) reaches 0.80. Browser scroll is scoped to an active popup if present; prefer browser_scroll for deterministic scrolling without inference."""
    return await _runtime.scroll_until_visible(target_description,direction,max_scrolls,mode)


@mcp.tool()
@guarded
async def visual_assert(questions: list[str], mode: Literal['browser','desktop']='browser') -> dict[str, Any]:
    """Evaluate up to 64 visual questions in one model call. answer=null means uncertain, not confirmation. Prefer DOM field labels and typed_verified for typing; avoid repeated visual assertions for an already verified action."""
    return await _runtime.visual_assert(questions,mode)


@mcp.tool()
@guarded
async def wait_until_ready(timeout_seconds: int=10, mode: Literal['browser','desktop']='browser') -> dict[str, Any]:
    """Wait for DOM readiness in hybrid mode, or visually in vision mode. Skip this call when browser_open returned ready=true. Readiness does not confirm task success or rule out a captcha."""
    return await _runtime.wait_until_ready(timeout_seconds,mode)


@mcp.tool()
@guarded
async def handle_popup(action: Literal['inspect','accept','reject','dismiss']='inspect', max_scrolls: int=8) -> dict[str, Any]:
    """Inspect a popup or explicitly accept/reject/dismiss it. Never assumes consent. Handles consent iframes and scrolls terms to unlock disabled buttons. Use the user's requested choice; reject never falls back to accept. popup_closed confirms closure; action_sent means do not repeat blindly."""
    return await _runtime.browser.popups.handle(action,max_scrolls)


@mcp.tool()
@guarded
async def browser_scroll(direction: Literal['down','up']='down', pixels: int=600, container: Literal['auto','page','popup']='auto') -> dict[str, Any]:
    """Scroll without visual inference. auto scrolls an active popup or its terms panel; otherwise the page. Returns moved and at_end. Use container=popup to prevent scrolling the underlying page."""
    return await _runtime.browser.popups.scroll(direction,pixels,container)


@mcp.tool()
@guarded
async def mouse_move(x: int, y: int, duration: float=.01, mode: Literal['desktop','browser']='desktop') -> dict[str, Any]:
    """Move without clicking. desktop moves the real OS pointer using global screen pixels; browser moves the tab's mouse using viewport pixels and syncs the real OS pointer on visible browsers. Prefer smart_move when only a target description is known."""
    return await _runtime.backend(mode).move(x,y,duration)


@mcp.tool()
@guarded
async def mouse_click(x: int | None=None, y: int | None=None, button: Literal['left','right','middle']='left', double_click: bool=False, mode: Literal['desktop','browser']='desktop') -> dict[str, Any]:
    """Click the real desktop pointer, optionally moving to global screen coordinates first. Browser mode requires x/y in the controlled tab viewport and moves the real OS pointer first. Use smart_click for semantic targets and handle_popup for an explicit consent choice."""
    return await _runtime.backend(mode).mouse_click(x,y,button,double_click)


@mcp.tool()
@guarded
async def smart_move(target_description: str, mode: Literal['desktop','browser']='desktop') -> dict[str, Any]:
    """Locate a described target and move/hover without clicking. Desktop mode uses a unique accessible control or D1 vision and the real OS pointer; browser mode uses DOM or D1 and moves both the tab mouse and the real OS pointer. Low confidence or a stale target prevents movement."""
    return await _runtime.smart_move(target_description,mode)


@mcp.tool()
@guarded
async def mouse_drag(start_x: int, start_y: int, end_x: int, end_y: int, button: Literal['left','right','middle']='left', duration: float=.12, mode: Literal['desktop','browser']='desktop') -> dict[str, Any]:
    """Move the pointer to (start_x, start_y), hold the mouse button, drag smoothly to (end_x, end_y), and release. Ideal for Paint tools, sliders, selections, and drag-and-drop."""
    return await _runtime.backend(mode).mouse_drag(start_x,start_y,end_x,end_y,button,duration)


@mcp.tool()
@guarded
async def desktop_inspect() -> dict[str, Any]:
    """Read-only platform requirements, accessible controls, and detected drawing canvas of the foreground app. Use exact labels in smart_click/type for the fast path; unavailable accessibility falls back to D1 vision."""
    snapshot=await _runtime.desktop.accessibility.snapshot()
    info=platform_info()
    canvas=None
    if info.get('desktop_supported'):
        try:
            canvas=await _runtime.desktop.detect_canvas()
        except Exception:
            canvas=None
    return {'status':'ok','platform':info,'accessibility_available':snapshot.get('available',False),
            'active_window':snapshot.get('window'),'canvas_bounds':canvas,'controls':snapshot.get('elements',[])[:40]}


@mcp.tool()
@guarded
async def draw_path(points: list[Any], canvas_bounds: list[int] | None=None, duration: float=.4, mode: Literal['desktop','browser']='desktop') -> dict[str, Any]:
    """Draw on a canvas by dragging the left mouse button. Accepts a single polyline [[x,y],...] or multiple strokes [[[x,y],...],...] (lifts the brush between strokes). Auto-detects the Paint/browser canvas sheet if canvas_bounds is omitted."""
    return await _runtime.backend(mode).draw_path(points,canvas_bounds,duration)


@mcp.tool()
@guarded
async def draw_shape(
    shape: Literal['line','rectangle','ellipse','circle','triangle','diamond','star','arrow','heart','house','spiral','wave'],
    x: int | None=None,
    y: int | None=None,
    width: int | None=None,
    height: int | None=None,
    canvas_bounds: list[int] | None=None,
    duration: float=.4,
    mode: Literal['desktop','browser']='desktop',
) -> dict[str, Any]:
    """Draw a shape (line, rectangle, ellipse, circle, triangle, diamond, star, arrow, heart, house, spiral, wave) by dragging the mouse on the sheet. Auto-detects canvas_bounds and centers the shape on the canvas if coordinates are omitted."""
    backend=_runtime.backend(mode)
    if canvas_bounds is None:
        canvas_bounds=await backend.detect_canvas()
    cx,cy,cw,ch=canvas_bounds
    w=max(16,round(cw*0.45)) if width is None else width
    h=max(16,round(ch*0.45)) if height is None else height
    sx=cx+max(2,(cw-w)//2) if x is None else x
    sy=cy+max(2,(ch-h)//2) if y is None else y
    return await backend.draw_path(shape_points(shape,sx,sy,w,h),canvas_bounds,duration)


def main():
    mcp.run(transport='stdio')


if __name__ == '__main__':
    main()
