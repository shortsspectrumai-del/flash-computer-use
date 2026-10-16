"""Lazy browser/desktop adapters; importing the MCP never opens a display."""
import asyncio
import io
import math
import os
import platform
import time
import threading
from PIL import Image
from .d1_engine import DecisionError
from .popups import Popups
from .desktop_accessibility import Accessibility
from .drawing import validate_path, human_path, normalize_strokes, interpolate_stroke, detect_canvas_from_image
from .portability import platform_info

_dpi_initialized = False


def _ensure_os_dpi_awareness():
    global _dpi_initialized
    if _dpi_initialized:
        return
    _dpi_initialized = True
    if platform.system() == 'Windows':
        try:
            import ctypes
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(2)
            except Exception:
                ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def _mouse_duration(default=0.04):
    try:
        val = float(os.getenv('D1_MOUSE_DURATION', str(default)))
        return val if math.isfinite(val) and 0 <= val <= 2 else default
    except ValueError:
        return default


def _fast_pyautogui():
    _ensure_os_dpi_awareness()
    import pyautogui
    if hasattr(pyautogui, 'PAUSE'):
        pyautogui.PAUSE = 0
    if hasattr(pyautogui, 'MINIMUM_DURATION'):
        pyautogui.MINIMUM_DURATION = 0
    if hasattr(pyautogui, 'MINIMUM_SLEEP'):
        pyautogui.MINIMUM_SLEEP = 0
    return pyautogui


def _move_pyautogui_human(pyautogui, target_x, target_y, duration=0.04, bounds=None):
    try:
        cur = pyautogui.position()
        start = (int(cur[0]), int(cur[1]))
    except Exception:
        start = (target_x, target_y)
    pts = human_path(start, (target_x, target_y), bounds=bounds)
    if len(pts) <= 1 or duration <= 0:
        pyautogui.moveTo(target_x, target_y, duration=max(0.0, duration))
        return
    step_dur = max(0.0, duration / len(pts))
    for px, py in pts[:-1]:
        pyautogui.moveTo(px, py, duration=0)
        if step_dur > 0.001:
            time.sleep(min(0.008, step_dur))
        try:
            if tuple(pyautogui.position()) != (px, py):
                return
        except Exception:
            pass
    pyautogui.moveTo(target_x, target_y, duration=0)


class Browser:
    def __init__(self):
        self.page = self.browser = self.playwright = None
        self.attached = False
        self._snapshot_handle = None
        self._blocked = None
        self._cursor_pos = (640, 400)
        self.popups = Popups(self)

    async def start(self):
        if self.page and not self.page.is_closed():
            return
        from playwright.async_api import async_playwright
        self.playwright = self.playwright or await async_playwright().start()
        cdp = os.getenv('D1_BROWSER_CDP_URL')
        if cdp:
            self.browser = await self.playwright.chromium.connect_over_cdp(cdp)
            self.attached = True
            pages = [p for c in self.browser.contexts for p in c.pages]
            url = os.getenv('D1_BROWSER_PAGE_URL')
            matches = [p for p in pages if p.url == url] if url else pages
            if len(matches) != 1:
                raise DecisionError('Set D1_BROWSER_PAGE_URL to an exact tab URL when attaching to multiple tabs')
            self.page = matches[0]
        else:
            self.browser = await self.playwright.chromium.launch(headless=os.getenv('D1_BROWSER_HEADLESS','false').lower() == 'true')
            self.page = await self.browser.new_page(viewport={'width':1280,'height':800}, device_scale_factor=1)
        self.page.on('response',self._navigation_response)

    def _navigation_response(self,response):
        if response.request.is_navigation_request() and response.frame==self.page.main_frame:
            action=response.headers.get('x-amzn-waf-action')
            self._blocked={'url':response.url,'block_reason':'waf_'+action} if action in {'challenge','captcha'} else None

    def block_status(self):
        if self._blocked and self.page and self.page.url.split('#')[0]==self._blocked['url'].split('#')[0]:
            return {'status':'blocked','block_reason':self._blocked['block_reason'],'ready':False}
        return None

    @staticmethod
    def _should_move_real_mouse():
        setting = os.getenv('D1_REAL_MOUSE', 'true').lower()
        if setting in {'0', 'false', 'no', 'off'}:
            return False
        if setting == 'always':
            return True
        return os.getenv('D1_BROWSER_HEADLESS', 'false').lower() != 'true'

    async def _sync_pointer(self, viewport_point, screen_point=None, duration=None):
        vx, vy = int(round(viewport_point[0])), int(round(viewport_point[1]))
        dur = _mouse_duration() if duration is None else duration
        if self.page and not self.page.is_closed():
            pts = human_path(self._cursor_pos, (vx, vy), bounds=(0, 0, 1280, 800))
            for px, py in pts:
                await self.page.mouse.move(px, py)
            self._cursor_pos = (vx, vy)
        if self._should_move_real_mouse():
            if screen_point is None and self.page and not self.page.is_closed():
                try:
                    screen_point = await self.page.evaluate('''([x,y])=>{
                        const bx=Math.max(0,Math.round((window.outerWidth-window.innerWidth)/2)),by=Math.max(0,Math.round(window.outerHeight-window.innerHeight-bx));
                        const sx=Math.round((window.mozInnerScreenX!==undefined?window.mozInnerScreenX:window.screenX+bx)+x);
                        const sy=Math.round((window.mozInnerScreenY!==undefined?window.mozInnerScreenY:window.screenY+by)+y);
                        return [sx,sy];
                    }''', [vx, vy])
                except Exception:
                    screen_point = None
            if screen_point is not None:
                await Desktop._move_real_pointer_safe(int(round(screen_point[0])), int(round(screen_point[1])), dur)

    async def open(self, url):
        if not url.startswith(('http://','https://')):
            raise ValueError('browser_open requires an http(s) URL')
        await self.start()
        await self.page.goto(url, wait_until='domcontentloaded')
        blocked=self.block_status()
        if blocked:
            return {**blocked,'url':self.page.url}
        elements, popup, meta = await asyncio.gather(
            self.candidates(),
            self.popups.inspect(),
            self.page.evaluate('''()=>{
                const visible=el=>{const r=el.getBoundingClientRect(),s=getComputedStyle(el);return s.display!=='none' && s.visibility==='visible' && Number(s.opacity)!==0 && r.width>0 && r.height>0 && r.bottom>0 && r.top<innerHeight && r.right>0 && r.left<innerWidth;};
                const body=document.body;
                const ready=document.readyState!=='loading' && !!body && visible(body)
                    && (!!body.innerText.trim() || [...body.querySelectorAll('input,button,canvas,img,video,svg')].some(visible))
                    && ![...document.querySelectorAll('[aria-busy="true"],[role="progressbar"],.loading-spinner,.skeleton')].some(visible);
                return {title:document.title||'',ready,preview:body?.innerText.slice(0,400)||''};
            }'''),
        )
        return {'status':'ok','popup':popup,'url':self.page.url,'page_title':meta['title'],
                'ready':False if self.block_status() else meta['ready'],
                'input_fields':[{'label':e['label'],'role':e['role']} for e in elements if e['editable']][:8],
                'page_text_preview':meta['preview']}

    async def capture(self):
        await self.start()
        raw = await self.page.screenshot(timeout=2000, animations='disabled', caret='hide')
        image = Image.open(io.BytesIO(raw))
        return (image if image.mode == 'RGB' else image.convert('RGB')), (0,0)

    async def candidates(self):
        await self.start()
        if self._snapshot_handle:
            await self._snapshot_handle.dispose()
        # Keep references to the actual nodes. A replacement with the same label
        # must never inherit a previously selected target.
        self._snapshot_handle = await self.page.evaluate_handle(r'''() => {
          const selector = 'button,a,input,textarea,select,summary,canvas,[role="button"],[role="link"],[role="searchbox"],[role="textbox"],[role="menuitem"],[role="tab"],[role="option"],[role="checkbox"],[role="radio"],[role="switch"],[role="combobox"],[contenteditable="true"]';
          const nodes = [...document.querySelectorAll(selector)];
          const probes = [[0.5,0.5],[0.35,0.5],[0.65,0.5],[0.5,0.35],[0.5,0.65],[0.25,0.5],[0.75,0.5]];
          const findHit = el => {
            const r = el.getBoundingClientRect();
            const x = Math.max(0,r.x), y = Math.max(0,r.y), right = Math.min(innerWidth,r.right), bottom = Math.min(innerHeight,r.bottom);
            if (right-x < 2 || bottom-y < 2) return null;
            const rects = [...el.getClientRects(), r];
            for (const rc of rects) {
              const rx = Math.max(0,rc.left), ry = Math.max(0,rc.top), rr = Math.min(innerWidth,rc.right), rb = Math.min(innerHeight,rc.bottom);
              if (rr-rx < 2 || rb-ry < 2) continue;
              for (const [fx,fy] of probes) {
                const px = rx+(rr-rx)*fx, py = ry+(rb-ry)*fy;
                const top = document.elementFromPoint(px,py);
                if (top && (el===top || el.contains(top) || (top.tagName==='LABEL' && top.contains(el)))) {
                  return {x, y, w: right-x, h: bottom-y, cx: px, cy: py};
                }
              }
            }
            return null;
          };
          const selected=[], elements=[];
          for (const el of nodes) {
            const s=getComputedStyle(el);
            if (el.disabled || el.getAttribute('aria-disabled')==='true' || s.visibility !== 'visible' || s.display === 'none' || Number(s.opacity) === 0) continue;
            const hit = findHit(el);
            if (!hit) continue;
            const labelled=(el.getAttribute('aria-labelledby')||'').split(/\s+/).map(id=>document.getElementById(id)?.textContent||'').join(' ').trim();
            const inputType=(el.type||'').toLowerCase();
            const valAlias=(['button','submit','reset'].includes(inputType)?el.value:'')||'';
            const aliases=[el.getAttribute('aria-label'),labelled,...[...(el.labels||[])].map(l=>l.innerText),el.innerText,el.placeholder,el.title,valAlias].filter(Boolean).map(a=>a.trim().slice(0,160)).filter(Boolean);
            const editable=!el.readOnly && (el.isContentEditable || el.tagName==='TEXTAREA' || (el.tagName==='INPUT' && !['button','submit','reset','checkbox','radio','file','hidden','image','range','color'].includes(inputType)));
            let role=el.getAttribute('role')||'';
            if (inputType==='search' || (editable && el.closest('[role="search"]'))) role='searchbox';
            const id=String(elements.length+1);
            selected.push(el);
            elements.push({id,label:aliases[0]||el.name||el.tagName,aliases,box:[hit.x,hit.y,hit.w,hit.h],editable,role,input_type:inputType});
            if (selected.length>=625) break;
          }
          const signature=el=>JSON.stringify([el.tagName,el.getAttribute('aria-label'),el.getAttribute('aria-labelledby'),el.innerText,el.placeholder,el.title,el.getAttribute('href'),el.type,...[...(el.labels||[])].map(l=>l.innerText)]);
          return {nodes:selected,elements,signature,signatures:selected.map(signature),findHit};
        }''')
        return await self._snapshot_handle.evaluate('(s)=>s.elements')

    async def snapshot(self):
        elements, (image, _) = await asyncio.gather(self.candidates(), self.capture())
        return image,elements

    async def interact_candidate(self,id,*,double=False,text=None,enter=False,hover=False):
        from playwright.async_api import Error as PlaywrightError
        handle=None
        try:
            if not self._snapshot_handle:
                return {'status':'stale_target'}
            state=await self._snapshot_handle.evaluate('''(s,id)=>{
                const i=Number(id)-1,el=s.nodes[i];
                if (!el || !el.isConnected || el.disabled || el.getAttribute('aria-disabled')==='true' || s.signature(el)!==s.signatures[i]) return null;
                const r=el.getBoundingClientRect();
                const hit=s.findHit ? s.findHit(el) : null;
                if(!hit) return null;
                const cx=hit.cx, cy=hit.cy;
                const vx=Math.round(cx),vy=Math.round(cy);
                const bx=Math.max(0,Math.round((window.outerWidth-window.innerWidth)/2)),by=Math.max(0,Math.round(window.outerHeight-window.innerHeight-bx));
                const sx=Math.round((window.mozInnerScreenX!==undefined?window.mozInnerScreenX:window.screenX+bx)+vx);
                const sy=Math.round((window.mozInnerScreenY!==undefined?window.mozInnerScreenY:window.screenY+by)+vy);
                return {point:[vx,vy],screen:[sx,sy],position:{x:cx-r.x,y:cy-r.y}};
            }''',id)
            if state is None:
                return {'status':'stale_target'}
            handle=await self._snapshot_handle.evaluate_handle('(s,id)=>s.nodes[Number(id)-1]',id)
            element=handle.as_element()
            if not element:
                return {'status':'stale_target'}
            # Always move both the real OS pointer and the browser cursor along a human-like curve to the target first.
            await self._sync_pointer(state['point'], state['screen'])
            if hover:
                await element.hover(position=state['position'],timeout=2000)
            elif text is not None:
                # Move & click/focus the field, replace previous content, and verify exact Unicode text.
                await element.fill(text,timeout=2000)
                actual=await element.evaluate("el=>el.isContentEditable ? el.innerText : el.value")
                if actual!=text:
                    return {'status':'typing_not_verified','typed_verified':False}
                if enter:
                    await element.press('Enter',timeout=2000,no_wait_after=True)
            elif double:
                await element.dblclick(position=state['position'],timeout=2000,no_wait_after=True)
            else:
                await element.click(position=state['position'],timeout=2000,no_wait_after=True)
            result={'status':'ok','clicked_coordinates':state['point']}
            if text is not None:
                result.update(typed_verified=True,typed_characters=len(text))
            return result
        except PlaywrightError:
            return {'status':'stale_or_blocked_target'}
        finally:
            if handle:
                await handle.dispose()

    async def readiness(self):
        await self.start()
        if self.block_status():
            return False
        return await self.page.evaluate('''()=>{
            const visible=el=>{const r=el.getBoundingClientRect(),s=getComputedStyle(el);return s.display!=='none' && s.visibility==='visible' && Number(s.opacity)!==0 && r.width>0 && r.height>0 && r.bottom>0 && r.top<innerHeight && r.right>0 && r.left<innerWidth;};
            const body=document.body;
            if(document.readyState==='loading' || !body || !visible(body)) return false;
            if(!body.innerText.trim() && ![...body.querySelectorAll('input,button,canvas,img,video,svg')].some(visible)) return false;
            return ![...document.querySelectorAll('[aria-busy="true"],[role="progressbar"],.loading-spinner,.skeleton')].some(visible);
        }''')

    async def click(self, x, y, double=False):
        await self._sync_pointer((x, y))
        if double:
            await self.page.mouse.dblclick(x,y)
        else:
            await self.page.mouse.click(x,y)

    async def _mouse_point(self,x,y):
        await self.start()
        if isinstance(x,bool) or isinstance(y,bool) or not isinstance(x,int) or not isinstance(y,int):
            raise ValueError('Mouse coordinates must be integer pixels inside the browser viewport')
        info=await self.page.evaluate('''([x,y])=>{
            const bx=Math.max(0,Math.round((window.outerWidth-window.innerWidth)/2)),by=Math.max(0,Math.round(window.outerHeight-window.innerHeight-bx));
            const sx=Math.round((window.mozInnerScreenX!==undefined?window.mozInnerScreenX:window.screenX+bx)+x);
            const sy=Math.round((window.mozInnerScreenY!==undefined?window.mozInnerScreenY:window.screenY+by)+y);
            return {width:innerWidth,height:innerHeight,screen:[sx,sy]};
        }''',[x,y])
        if not 0<=x<info['width'] or not 0<=y<info['height']:
            raise ValueError('Mouse coordinates must be integer pixels inside the browser viewport')
        return info['screen']

    async def move(self,x,y,duration=.04):
        if not math.isfinite(duration) or not 0<=duration<=2:
            raise ValueError('Mouse duration must be 0..2 seconds')
        screen=await self._mouse_point(x,y)
        await self._sync_pointer((x,y),screen,duration=duration)
        return {'status':'ok','moved_coordinates':[x,y],'mode':'browser'}

    async def mouse_click(self,x=None,y=None,button='left',double_click=False):
        if x is None or y is None:
            raise ValueError('Browser mouse_click requires both x and y')
        if button not in {'left','right','middle'}:
            raise ValueError('Invalid mouse button')
        screen=await self._mouse_point(x,y)
        await self._sync_pointer((x,y),screen)
        await self.page.mouse.click(x,y,button=button,click_count=2 if double_click else 1)
        return {'status':'ok','clicked_coordinates':[x,y],'button':button,'mode':'browser'}

    async def type(self, text, enter):
        await self.page.keyboard.insert_text(text)
        if enter:
            await self.page.keyboard.press('Enter')

    async def scroll(self, direction):
        await self.start()
        result=await self.popups.scroll(direction,600,'auto')
        await asyncio.sleep(.01)
        return result

    async def detect_canvas(self):
        await self.start()
        bounds = await self.page.evaluate('''()=>{
            const nodes=[...document.querySelectorAll('canvas,[data-canvas],[id*="canvas" i],[class*="canvas" i],[role="img"],svg')];
            let best=null,bestArea=0;
            for(const el of nodes){
                const r=el.getBoundingClientRect(),s=getComputedStyle(el);
                if(s.display==='none'||s.visibility!=='visible'||Number(s.opacity)===0) continue;
                const x=Math.max(0,Math.round(r.x)),y=Math.max(0,Math.round(r.y));
                const right=Math.min(innerWidth,Math.round(r.right)),bottom=Math.min(innerHeight,Math.round(r.bottom));
                const w=right-x,h=bottom-y,area=w*h;
                if(w>=32 && h>=32 && area>bestArea){bestArea=area;best=[x,y,w,h];}
            }
            return best || [Math.round(innerWidth*0.05),Math.round(innerHeight*0.05),Math.round(innerWidth*0.9),Math.round(innerHeight*0.9)];
        }''')
        return [int(v) for v in bounds]

    async def mouse_drag(self,start_x,start_y,end_x,end_y,button='left',duration=.12):
        if button not in {'left','right','middle'}:
            raise ValueError('Invalid mouse button')
        if not math.isfinite(duration) or not 0<=duration<=10:
            raise ValueError('Drag duration must be 0..10 seconds')
        start_screen=await self._mouse_point(start_x,start_y)
        end_screen=await self._mouse_point(end_x,end_y)
        await self._sync_pointer((start_x,start_y),start_screen)
        drag_pts=interpolate_stroke([[start_x,start_y],[end_x,end_y]],step_px=8)
        await self.page.mouse.down(button=button)
        try:
            step_sleep=duration/max(1,len(drag_pts)-1) if duration else 0
            for px,py in drag_pts[1:]:
                self._cursor_pos=(px,py)
                await self.page.mouse.move(px,py)
                if step_sleep:
                    await asyncio.sleep(step_sleep)
            if self._should_move_real_mouse() and end_screen:
                await Desktop._move_real_pointer_safe(end_screen[0],end_screen[1],0)
        finally:
            await self.page.mouse.up(button=button)
        return {'status':'ok','start_coordinates':[start_x,start_y],'end_coordinates':[end_x,end_y],'button':button,'mode':'browser'}

    async def draw_path(self,points,canvas_bounds=None,duration=2):
        if canvas_bounds is None:
            canvas_bounds=await self.detect_canvas()
        strokes=normalize_strokes(points,canvas_bounds)
        if not math.isfinite(duration) or not 0<=duration<=30:
            raise ValueError('Drawing duration must be 0..30 seconds')
        all_points=[pt for stroke in strokes for pt in stroke]
        first_screen=await self._mouse_point(*all_points[0])
        for x,y in all_points[1:]:
            await self._mouse_point(x,y)
        total_drawn=0
        stroke_dur=duration/len(strokes) if duration else 0
        for idx,stroke in enumerate(strokes):
            smooth=interpolate_stroke(stroke,step_px=8) if stroke_dur>0 else stroke
            await self._sync_pointer(smooth[0],first_screen if idx==0 else None,duration=0)
            await self.page.mouse.down()
            try:
                step_sleep=stroke_dur/max(1,len(smooth)-1) if stroke_dur else 0
                for x,y in smooth[1:]:
                    self._cursor_pos=(x,y)
                    await self.page.mouse.move(x,y)
                    if step_sleep:
                        await asyncio.sleep(step_sleep)
            finally:
                await self.page.mouse.up()
            total_drawn+=len(stroke)
        if self._should_move_real_mouse():
            await self._sync_pointer(all_points[-1],duration=0)
        return {'status':'ok','points_drawn':total_drawn,'strokes_drawn':len(strokes),'canvas_bounds':canvas_bounds,'mode':'browser'}

    async def close(self):
        if self._snapshot_handle:
            await self._snapshot_handle.dispose()
            self._snapshot_handle = None
        if self.browser and not self.attached:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()


class Desktop:
    def __init__(self):
        _ensure_os_dpi_awareness()
        self.accessibility=Accessibility()

    @staticmethod
    def _ensure_supported():
        status=platform_info()
        if not status['desktop_supported']:
            raise DecisionError(status['note'])

    @staticmethod
    def _get_monitors():
        _ensure_os_dpi_awareness()
        try:
            import mss
            with mss.mss() as screen:
                mons = list(screen.monitors[1:])
                if mons:
                    return mons
        except Exception:
            pass
        if platform.system()=='Darwin':
            pyautogui=_fast_pyautogui()
            width,height=pyautogui.size()
            return [{'left':0,'top':0,'width':width,'height':height}]
        return []

    @staticmethod
    async def _move_real_pointer_safe(sx, sy, duration=0.04):
        if not platform_info()['desktop_supported']:
            return
        def _move():
            try:
                monitors = Desktop._get_monitors()
                if not monitors:
                    return
                m = next((m for m in monitors if m['left']<=sx<m['left']+m['width'] and m['top']<=sy<m['top']+m['height']), monitors[0])
                cx = max(m['left']+2, min(m['left']+m['width']-3, sx))
                cy = max(m['top']+2, min(m['top']+m['height']-3, sy))
                bounds = (m['left']+2, m['top']+2, max(1, m['width']-4), max(1, m['height']-4))
                pyautogui = _fast_pyautogui()
                _move_pyautogui_human(pyautogui, cx, cy, duration=duration, bounds=bounds)
            except Exception:
                pass
        await asyncio.to_thread(_move)

    async def accessible_target(self,description,editable_only=False):
        self._ensure_supported()
        return await self.accessibility.target(description,editable_only)

    async def interact_accessible(self,target,hover=False,double=False):
        if not await self.accessibility.validate(target):
            return {'status':'stale_accessible_target'}
        x,y,w,h=target['box']
        point=(round(x+w/2),round(y+h/2))
        if hover:
            return await self.move(*point,duration=_mouse_duration())
        result=await self.mouse_click(*point,double_click=double)
        result.update(ui_changed=None,verification_pending=True)
        return result

    async def detect_canvas(self):
        self._ensure_supported()
        snapshot=await self.accessibility.snapshot()
        canvas_roles={'canvas','drawing area','image','viewport','document frame','document','pane','custom','aximage','axscrollarea','axlayoutarea'}
        candidates=[
            e['box'] for e in snapshot.get('elements',[])
            if e.get('role') in canvas_roles and e['box'][2]>=100 and e['box'][3]>=100
        ]
        if candidates:
            best=max(candidates,key=lambda b:b[2]*b[3])
            return [int(best[0])+2,int(best[1])+2,max(16,int(best[2])-4),max(16,int(best[3])-4)]
        image,origin=await self.capture()
        return detect_canvas_from_image(image,origin)

    async def capture(self):
        self._ensure_supported()
        def grab():
            _ensure_os_dpi_awareness()
            import mss
            with mss.mss() as screen:
                idx = int(os.getenv('D1_MONITOR','1'))
                if not 1 <= idx < len(screen.monitors):
                    idx = 1
                monitor = screen.monitors[idx]
                shot = screen.grab(monitor)
                image = Image.frombytes('RGB',shot.size,shot.rgb)
                logical = (monitor['width'], monitor['height'])
                if platform.system()=='Darwin' and idx==1 and monitor['left']==0 and monitor['top']==0:
                    try:
                        pyautogui=_fast_pyautogui()
                        logical=tuple(pyautogui.size())
                    except Exception:
                        pass
                if logical[0]>0 and logical[1]>0 and image.size!=logical:
                    image=image.resize(logical,Image.Resampling.BILINEAR)
                return image,(monitor['left'],monitor['top'])
        return await asyncio.to_thread(grab)

    @staticmethod
    def _validate_points(points):
        Desktop._ensure_supported()
        if any(isinstance(v,bool) or not isinstance(v,int) for point in points for v in point):
            raise ValueError('Mouse coordinates must be integer screen pixels')
        monitors=Desktop._get_monitors()
        if not all(any(m['left']<=x<m['left']+m['width'] and m['top']<=y<m['top']+m['height'] for m in monitors) for x,y in points):
            raise ValueError('Mouse coordinates are outside the connected monitors')

    @staticmethod
    def _validate_point(x,y):
        Desktop._validate_points([(x,y)])

    async def move(self,x,y,duration=.04):
        if not math.isfinite(duration) or not 0<=duration<=2:
            raise ValueError('Mouse duration must be 0..2 seconds')
        def move():
            pyautogui=_fast_pyautogui()
            self._validate_point(x,y)
            _move_pyautogui_human(pyautogui, x, y, duration=duration)
            position=list(pyautogui.position())
            return {'status':'ok' if position==[x,y] else 'interrupted','moved_coordinates':position,'mode':'desktop'}
        return await asyncio.to_thread(move)

    async def mouse_click(self,x=None,y=None,button='left',double_click=False):
        if (x is None)!=(y is None):
            raise ValueError('Provide both x and y, or neither for the current desktop pointer')
        if button not in {'left','right','middle'}:
            raise ValueError('Invalid mouse button')
        def click():
            pyautogui=_fast_pyautogui()
            px,py=pyautogui.position() if x is None else (x,y)
            self._validate_point(px,py)
            if x is not None:
                _move_pyautogui_human(pyautogui, px, py, duration=_mouse_duration())
                if tuple(pyautogui.position())!=(px,py):
                    return {'status':'interrupted'}
            pyautogui.click(clicks=2 if double_click else 1,interval=.03,button=button)
            return {'status':'ok','clicked_coordinates':[px,py],'button':button,'mode':'desktop'}
        return await asyncio.to_thread(click)

    async def click(self,x,y,double=False):
        return await self.mouse_click(x,y,double_click=double)

    async def mouse_drag(self,start_x,start_y,end_x,end_y,button='left',duration=.12):
        if button not in {'left','right','middle'}:
            raise ValueError('Invalid mouse button')
        if not math.isfinite(duration) or not 0<=duration<=10:
            raise ValueError('Drag duration must be 0..10 seconds')
        cancelled=threading.Event()
        def drag():
            pyautogui=_fast_pyautogui()
            self._validate_points([(start_x,start_y),(end_x,end_y)])
            _move_pyautogui_human(pyautogui,start_x,start_y,duration=_mouse_duration())
            pts=interpolate_stroke([[start_x,start_y],[end_x,end_y]],step_px=8)
            try:
                pyautogui.mouseDown(button=button,_pause=False)
                step_wait=duration/max(1,len(pts)-1) if duration else 0
                for px,py in pts[1:]:
                    if cancelled.is_set():
                        break
                    pyautogui.moveTo(px,py,_pause=False)
                    if step_wait:
                        cancelled.wait(step_wait)
            finally:
                was_failsafe=getattr(pyautogui,'FAILSAFE',True)
                try:
                    pyautogui.FAILSAFE=False
                    pyautogui.mouseUp(button=button,_pause=False)
                finally:
                    pyautogui.FAILSAFE=was_failsafe
            return {'status':'interrupted' if cancelled.is_set() else 'ok','start_coordinates':[start_x,start_y],'end_coordinates':[end_x,end_y],'button':button,'mode':'desktop'}
        try:
            return await asyncio.to_thread(drag)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    async def type(self,text,enter,replace=False):
        def type_text():
            pyautogui=_fast_pyautogui()
            modifier='command' if platform.system()=='Darwin' else 'ctrl'
            if replace:
                pyautogui.hotkey(modifier,'a')
            pasted = False
            try:
                import pyperclip
                previous = pyperclip.paste()
                try:
                    pyperclip.copy(text)
                    pyautogui.hotkey(modifier,'v')
                    time.sleep(.02)
                    pasted = True
                finally:
                    pyperclip.copy(previous)
            except Exception:
                if hasattr(pyautogui, 'write'):
                    pyautogui.write(text, interval=0.005)
                    pasted = True
            if not pasted and hasattr(pyautogui, 'write'):
                pyautogui.write(text, interval=0.005)
            if enter:
                pyautogui.press('enter')
        await asyncio.to_thread(type_text)

    async def draw_path(self,points,canvas_bounds=None,duration=2):
        if canvas_bounds is None:
            canvas_bounds=await self.detect_canvas()
        strokes=normalize_strokes(points,canvas_bounds)
        if not math.isfinite(duration) or not 0<=duration<=30:
            raise ValueError('Drawing duration must be 0..30 seconds')
        all_points=[pt for stroke in strokes for pt in stroke]
        cancelled=threading.Event()
        def draw():
            pyautogui=_fast_pyautogui()
            self._validate_points(all_points)
            total_drawn=0
            stroke_dur=duration/len(strokes) if duration else 0
            for stroke in strokes:
                if cancelled.is_set():
                    break
                smooth=interpolate_stroke(stroke,step_px=8) if stroke_dur>0 else stroke
                pyautogui.moveTo(*smooth[0],_pause=False)
                try:
                    pyautogui.mouseDown(_pause=False)
                    step_wait=stroke_dur/max(1,len(smooth)-1) if stroke_dur else 0
                    for x,y in smooth[1:]:
                        if cancelled.is_set():
                            break
                        pyautogui.moveTo(x,y,_pause=False)
                        if step_wait:
                            cancelled.wait(step_wait)
                finally:
                    # Release even on fail-safe or interruption. FAILSAFE stays active
                    # for moves; releasing a held button must always be possible.
                    was_failsafe=pyautogui.FAILSAFE
                    try:
                        pyautogui.FAILSAFE=False
                        pyautogui.mouseUp(_pause=False)
                    finally:
                        pyautogui.FAILSAFE=was_failsafe
                total_drawn+=len(stroke)
            return {'status':'interrupted' if cancelled.is_set() else 'ok','points_drawn':total_drawn,'strokes_drawn':len(strokes),'canvas_bounds':canvas_bounds,'mode':'desktop'}
        try:
            return await asyncio.to_thread(draw)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    async def scroll(self,direction):
        def scroll():
            pyautogui=_fast_pyautogui()
            try:
                px,py=pyautogui.position()
                monitors=self._get_monitors()
                if monitors and not any(m['left']<=px<m['left']+m['width'] and m['top']<=py<m['top']+m['height'] for m in monitors):
                    m=monitors[0]
                    _move_pyautogui_human(pyautogui, m['left']+m['width']//2, m['top']+m['height']//2, duration=_mouse_duration())
            except Exception:
                pass
            pyautogui.scroll(-6 if direction=='down' else 6)
        await asyncio.to_thread(scroll)
        await asyncio.sleep(.02)
