import os
from pathlib import Path
import pytest
from d1_computer_use_mcp.backends import Browser
from d1_computer_use_mcp.actions import ComputerUse
from d1_computer_use_mcp.d1_engine import Settings


@pytest.mark.asyncio
async def test_browser_dom_click_and_unicode_input(monkeypatch):
    browsers = Path('.runtime/playwright').resolve()
    if not list(browsers.glob('chromium_headless_shell-*')):
        pytest.skip('Run playwright install chromium first')
    monkeypatch.setenv('PLAYWRIGHT_BROWSERS_PATH',str(browsers))
    monkeypatch.setenv('D1_BROWSER_HEADLESS','true')
    monkeypatch.delenv('D1_BROWSER_CDP_URL',raising=False)
    browser = Browser()
    class Choose:
        settings = Settings()
        async def ask_choice(self,image,question,options):
            target = 'Name' if 'Name' in question else 'Login'
            selected = next(k for k,v in options.items() if v==target)
            return {'choice':selected,'confidence':.99,'confidence_source':'test'}
    try:
        await browser.start()
        await browser.page.set_content('<button onclick="this.textContent=\'Done\'">Login</button><input aria-label="Name">')
        actions = ComputerUse(Choose(),browser,None)
        result = await actions.smart_click('Login')
        assert result['status']=='ok'
        assert await browser.page.locator('button').inner_text() == 'Done'
        result = await actions.smart_type('Name','Città 日本',press_enter=False)
        assert result['status']=='ok'
        assert await browser.page.locator('input').input_value()=='Città 日本'
    finally:
        await browser.close()


@pytest.mark.asyncio
async def test_dense_page_search_is_precise_without_inference(monkeypatch):
    monkeypatch.setenv('PLAYWRIGHT_BROWSERS_PATH',str(Path('.runtime/playwright').resolve()))
    monkeypatch.setenv('D1_BROWSER_HEADLESS','true')
    monkeypatch.delenv('D1_BROWSER_CDP_URL',raising=False)
    class NoInference:
        settings=Settings()
        async def ask_choice(self,*args):
            raise AssertionError('Exact DOM targets must not need D1')
        async def ask_yes_no(self,*args):
            raise AssertionError('DOM readiness must not need D1')
    browser=Browser()
    try:
        await browser.start()
        await browser.page.set_content('<input aria-label="Email"><input type="search" aria-label="Cerca in Amazon.it" value="old query"><button>Cerca in Amazon.it</button>'+''.join(f'<a href="#">Item {i}</a>' for i in range(40)))
        actions=ComputerUse(NoInference(),browser,None)
        ready=await actions.wait_until_ready()
        assert ready['status']=='ready'
        result=await actions.smart_type('barra di ricerca di Amazon (campo "Cerca in Amazon")','Città 日本',False)
        assert result['status']=='ok'
        assert result['typed_verified'] is True
        assert result['method']=='dom'
        assert await browser.page.locator('input[type=search]').input_value()=='Città 日本'
        assert await browser.page.locator('input[aria-label=Email]').input_value()==''
    finally:
        await browser.close()


@pytest.mark.asyncio
async def test_detached_candidate_cannot_click_replacement(monkeypatch):
    monkeypatch.setenv('PLAYWRIGHT_BROWSERS_PATH',str(Path('.runtime/playwright').resolve()))
    monkeypatch.setenv('D1_BROWSER_HEADLESS','true')
    browser=Browser()
    try:
        await browser.start()
        await browser.page.set_content('<button onclick="window.wrong=true">Login</button>')
        elements=await browser.candidates()
        await browser.page.locator('button').evaluate('(el)=>el.outerHTML=\'<button onclick="window.wrong=true">Login</button>\'')
        result=await browser.interact_candidate(elements[0]['id'])
        assert result['status']=='stale_target'
        assert await browser.page.evaluate('window.wrong !== true')
    finally:
        await browser.close()


@pytest.mark.asyncio
async def test_renamed_candidate_cannot_receive_old_click(monkeypatch):
    monkeypatch.setenv('PLAYWRIGHT_BROWSERS_PATH',str(Path('.runtime/playwright').resolve()))
    monkeypatch.setenv('D1_BROWSER_HEADLESS','true')
    browser=Browser()
    try:
        await browser.start()
        await browser.page.set_content('<button onclick="window.wrong=true">Login</button>')
        elements=await browser.candidates()
        await browser.page.locator('button').evaluate('(el)=>el.textContent="Delete account"')
        result=await browser.interact_candidate(elements[0]['id'])
        assert result['status']=='stale_target'
        assert await browser.page.evaluate('window.wrong !== true')
    finally:
        await browser.close()


@pytest.mark.asyncio
async def test_waf_challenge_reported_without_waiting(monkeypatch):
    monkeypatch.setenv('PLAYWRIGHT_BROWSERS_PATH',str(Path('.runtime/playwright').resolve()))
    monkeypatch.setenv('D1_BROWSER_HEADLESS','true')
    browser=Browser()
    try:
        await browser.start()
        await browser.page.route('https://shop.test/**',lambda route:route.fulfill(status=202,headers={'x-amzn-waf-action':'challenge'},body='<html><body></body></html>'))
        result=await browser.open('https://shop.test/')
        assert result['status']=='blocked'
        assert result['block_reason']=='waf_challenge'
        assert result['ready'] is False
        result=await ComputerUse(type('Engine',(),{'settings':Settings()})(),browser,None).wait_until_ready()
        assert result['status']=='blocked'
    finally:
        await browser.close()


@pytest.mark.asyncio
async def test_post_action_screenshot_failure_does_not_repeat_typing(monkeypatch):
    from playwright.async_api import Error
    monkeypatch.setenv('PLAYWRIGHT_BROWSERS_PATH',str(Path('.runtime/playwright').resolve()))
    monkeypatch.setenv('D1_BROWSER_HEADLESS','true')
    browser=Browser()
    try:
        await browser.start()
        await browser.page.set_content('<input aria-label="Search">')
        capture=browser.capture
        calls=0
        async def unstable_capture():
            nonlocal calls
            calls+=1
            if calls==2:
                raise Error('Navigation interrupted screenshot')
            return await capture()
        monkeypatch.setattr(browser,'capture',unstable_capture)
        actions=ComputerUse(type('Engine',(),{'settings':Settings()})(),browser,None)
        result=await actions.smart_type('Search','exact query',False)
        assert result['status']=='ok'
        assert result['typed_verified'] is True
        assert result['verification_pending'] is True
        assert result['ui_changed'] is None
        assert await browser.page.locator('input').input_value()=='exact query'
    finally:
        await browser.close()


@pytest.mark.asyncio
async def test_smart_hover_and_browser_coordinate_click(monkeypatch):
    monkeypatch.setenv('PLAYWRIGHT_BROWSERS_PATH',str(Path('.runtime/playwright').resolve()))
    monkeypatch.setenv('D1_BROWSER_HEADLESS','true')
    browser=Browser()
    try:
        await browser.start()
        await browser.page.set_content('<button style="margin:100px;padding:40px" onmouseover="window.hovered=true" onclick="window.clicked=true">Login</button>')
        actions=ComputerUse(type('Engine',(),{'settings':Settings()})(),browser,None)
        moved=await actions.smart_move('Login','browser')
        assert moved['status']=='ok'
        assert await browser.page.evaluate('window.hovered === true && window.clicked !== true')
        clicked=await browser.mouse_click(*moved['moved_coordinates'])
        assert clicked['status']=='ok'
        assert await browser.page.evaluate('window.clicked === true')
    finally:
        await browser.close()


@pytest.mark.asyncio
async def test_drawing_stroke_on_canvas_and_rejects_outside(monkeypatch):
    monkeypatch.setenv('PLAYWRIGHT_BROWSERS_PATH',str(Path('.runtime/playwright').resolve()))
    monkeypatch.setenv('D1_BROWSER_HEADLESS','true')
    browser=Browser()
    try:
        await browser.start()
        await browser.page.set_content('''<style>body{margin:0}</style><canvas width="400" height="300"></canvas><script>
        const c=document.querySelector('canvas'),ctx=c.getContext('2d');let down=false;
        c.onmousedown=e=>{down=true;ctx.beginPath();ctx.moveTo(e.offsetX,e.offsetY)};
        c.onmousemove=e=>{if(down){ctx.lineTo(e.offsetX,e.offsetY);ctx.stroke()}};
        window.onmouseup=()=>{down=false;window.released=true};</script>''')
        result=await browser.draw_path([[50,50],[150,50],[150,150]],[0,0,400,300],0)
        assert result['status']=='ok'
        assert await browser.page.evaluate("document.querySelector('canvas').getContext('2d').getImageData(100,50,1,1).data[3]>0")
        assert await browser.page.evaluate('window.released===true')
        with pytest.raises(ValueError):
            await browser.draw_path([[50,50],[500,50]],[0,0,400,300],0)
    finally:
        await browser.close()


@pytest.mark.asyncio
async def test_partially_occluded_center_clicks_unoccluded_point(monkeypatch):
    monkeypatch.setenv('PLAYWRIGHT_BROWSERS_PATH',str(Path('.runtime/playwright').resolve()))
    monkeypatch.setenv('D1_BROWSER_HEADLESS','true')
    browser=Browser()
    try:
        await browser.start()
        await browser.page.set_content('''
            <div style="position:relative;width:200px;height:60px">
                <button style="width:200px;height:60px" onclick="window.clicked=true">Checkout</button>
                <div style="position:absolute;left:85px;top:15px;width:30px;height:30px;background:red;z-index:5" onclick="window.blocker=true"></div>
            </div>
        ''')
        actions=ComputerUse(type('Engine',(),{'settings':Settings()})(),browser,None)
        result=await actions.smart_click('Checkout','browser')
        assert result['status']=='ok'
        assert await browser.page.evaluate('window.clicked === true && window.blocker !== true')
    finally:
        await browser.close()


@pytest.mark.asyncio
async def test_auto_canvas_detection_and_mouse_drag(monkeypatch):
    monkeypatch.setenv('PLAYWRIGHT_BROWSERS_PATH',str(Path('.runtime/playwright').resolve()))
    monkeypatch.setenv('D1_BROWSER_HEADLESS','true')
    browser=Browser()
    try:
        await browser.start()
        await browser.page.set_content('''<style>body{margin:0}</style><canvas id="sheet" width="500" height="350" style="margin:20px"></canvas><script>
        const c=document.querySelector('canvas'),ctx=c.getContext('2d');let down=false;window.strokes=0;
        c.onmousedown=e=>{down=true;window.strokes++;ctx.beginPath();ctx.moveTo(e.offsetX,e.offsetY)};
        c.onmousemove=e=>{if(down){ctx.lineTo(e.offsetX,e.offsetY);ctx.stroke()}};
        window.onmouseup=()=>{down=false};</script>''')
        bounds=await browser.detect_canvas()
        assert bounds==[20,20,500,350]
        # Multi-stroke drawing without passing canvas_bounds explicitly
        res=await browser.draw_path([[[40,40],[120,40]],[[40,100],[120,100]]],None,0)
        assert res['status']=='ok'
        assert res['strokes_drawn']==2
        assert res['canvas_bounds']==[20,20,500,350]
        drag=await browser.mouse_drag(50,150,150,150,duration=0)
        assert drag['status']=='ok'
        assert await browser.page.evaluate('window.strokes===3')
    finally:
        await browser.close()


@pytest.mark.asyncio
async def test_card_context_svg_icon_select_and_hybrid_scroll(monkeypatch):
    monkeypatch.setenv('PLAYWRIGHT_BROWSERS_PATH',str(Path('.runtime/playwright').resolve()))
    monkeypatch.setenv('D1_BROWSER_HEADLESS','true')
    class NoInference:
        settings=Settings()
        async def ask_choice(self,*args):
            raise AssertionError('Should resolve deterministically via DOM context/icon/select')
        async def ask_yes_no(self,*args):
            raise AssertionError('Should resolve scroll_until_visible via DOM')
    browser=Browser()
    try:
        await browser.start()
        await browser.page.set_content('''
            <header>
                <button onclick="window.cartClicked=true"><svg aria-label="Shopping Cart"></svg></button>
                <select aria-label="Sort order" onchange="window.sorted=this.value">
                    <option value="featured">Featured</option>
                    <option value="price_asc">Price: Low to High</option>
                </select>
            </header>
            <main>
                <article><h3>Starter Kit</h3><button onclick="window.picked=1">Select Plan</button></article>
                <article><h3>Enterprise Suite</h3><button onclick="window.picked=2">Select Plan</button></article>
                <div style="height:1400px"></div>
                <button id="bottom-btn" onclick="window.bottomClicked=true">Load More Results</button>
            </main>
        ''')
        actions=ComputerUse(NoInference(),browser,None)
        # 1. SVG icon button resolved via child aria-label
        r1=await actions.smart_click('Shopping Cart','browser')
        assert r1['status']=='ok' and r1['method']=='dom'
        assert await browser.page.evaluate('window.cartClicked === true')
        # 2. Duplicate "Select Plan" button disambiguated by enclosing article heading
        r2=await actions.smart_click('Select Plan for Enterprise Suite','browser')
        assert r2['status']=='ok' and r2['method']=='dom'
        assert await browser.page.evaluate('window.picked === 2')
        # 3. <select> dropdown option selection via smart_type
        r3=await actions.smart_type('Sort order','Price: Low to High',press_enter=False,mode='browser')
        assert r3['status']=='ok' and r3['typed_verified'] is True
        assert await browser.page.evaluate('window.sorted === "price_asc"')
        # 4. Hybrid scroll_until_visible finds offscreen button via DOM without VLM call
        r4=await actions.scroll_until_visible('Load More Results',direction='down',max_scrolls=5,mode='browser')
        assert r4['status']=='visible' and r4['method']=='dom' and r4['scrolls']>=1
    finally:
        await browser.close()


@pytest.mark.asyncio
async def test_d1_synergy_narrows_and_crops_ambiguous_candidates_on_dense_page(monkeypatch):
    monkeypatch.setenv('PLAYWRIGHT_BROWSERS_PATH',str(Path('.runtime/playwright').resolve()))
    monkeypatch.setenv('D1_BROWSER_HEADLESS','true')
    calls=[]
    class SynergyEngine:
        settings=Settings()
        async def ask_choice(self,image,question,options):
            calls.append((image.size, options))
            # Pick the second Buy Now button based on contextual option description
            chosen=next(k for k,v in options.items() if k!='none' and 'Studio Monitor' in v)
            return {'choice':chosen,'confidence':.95,'confidence_source':'calibrated_d1'}
    browser=Browser()
    try:
        await browser.start()
        nav=''.join(f'<a href="#c{i}" style="margin:4px;display:inline-block">Category {i}</a>' for i in range(40))
        await browser.page.set_content(f'''
            <nav>{nav}</nav>
            <main style="margin-top:40px;display:flex;gap:20px">
                <article style="width:220px;height:120px"><h3>USB Microphone</h3><button onclick="window.bought=1">Buy Now</button></article>
                <article style="width:220px;height:120px"><h3>Studio Monitor</h3><button onclick="window.bought=2">Buy Now</button></article>
            </main>
        ''')
        actions=ComputerUse(SynergyEngine(),browser,None)
        result=await actions.smart_click('Buy Now','browser')
        assert result['status']=='ok' and result['method']=='d1'
        assert await browser.page.evaluate('window.bought === 2')
        # Even though the page has 42 elements, select_d1_candidates narrowed it to the 2 "Buy Now" buttons in a single cropped D1 call!
        assert len(calls)==1
        img_size, opts = calls[0]
        assert len([k for k in opts if k!='none'])==2
        assert img_size[0] < 1280 and img_size[1] < 800
    finally:
        await browser.close()
