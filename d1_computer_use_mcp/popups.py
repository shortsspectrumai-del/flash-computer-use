"""Explicit popup choices and bounded scrolling, including consent frames."""
import asyncio
from urllib.parse import urlparse
from .targeting import normalize

ROOTS = 'dialog[open],[role="dialog"],[aria-modal="true"],#onetrust-banner-sdk,.qc-cmp2-container,[id*="cookie-banner" i],[id*="consent-banner" i]'
CONTROLS = 'button,a[href],input[type="button"],input[type="submit"],[role="button"]'
LABELS = {
    'accept': {'accetta','accetta tutto','accetta tutti','accetto','accetta e continua','accept','accept all','accept and continue','i agree','agree','allow all','consenti tutto','accetta l utilizzo dei cookie e di altri dati per le finalità descritte'},
    'reject': {'rifiuta','rifiuta tutto','rifiuta tutti','reject','reject all','decline','decline all','non accetto','non accettare','solo necessari','accetta solo necessari','only necessary','necessary only','reject optional cookies','continua senza accettare','rifiuta l utilizzo dei cookie e di altri dati per le finalità descritte'},
    'dismiss': {'chiudi','close','dismiss','not now','non ora','no grazie','no thanks','x'},
}


def classify(label):
    key=normalize(label)
    if label.strip() in {'×','✕'}:
        return 'dismiss'
    return next((action for action,labels in LABELS.items() if key in labels),None)


class Popups:
    def __init__(self,browser):
        self.browser=browser

    async def _find(self):
        from playwright.async_api import Error
        await self.browser.start()
        found=[]
        for frame in self.browser.page.frames:
            try:
                if frame.parent_frame:
                    iframe=await frame.frame_element()
                    try:
                        if not await iframe.is_visible():
                            continue
                    finally:
                        await iframe.dispose()
                roots=await frame.locator(ROOTS).element_handles()
                if not roots and urlparse(frame.url).hostname in {'consent.youtube.com','consent.google.com'}:
                    roots=await frame.locator('body').element_handles()
                for root in roots:
                    visible=await root.evaluate('''(el,selector)=>{
                        const r=el.getBoundingClientRect(),s=getComputedStyle(el);
                        if(s.display==='none'||s.visibility!=='visible'||Number(s.opacity)===0||r.width<2||r.height<2||r.bottom<=0||r.top>=innerHeight) return false;
                        if(el.parentElement?.closest(selector)) return false;
                        const x=Math.max(0,Math.min(innerWidth-1,r.x+r.width/2)),y=Math.max(0,Math.min(innerHeight-1,r.y+r.height/2));
                        const top=document.elementFromPoint(x,y);
                        return !!top && (el===top || el.contains(top));
                    }''',ROOTS)
                    if visible:
                        found.append(root)
                    else:
                        await root.dispose()
            except Error:
                continue
        if len(found)==1:
            return found[0],None
        for root in found:
            await root.dispose()
        return None,{'status':'ambiguous_popup' if found else 'no_popup','popup_count':len(found)}

    async def _describe(self,root):
        info=await root.evaluate('''(root,selector)=>{
            const visible=el=>{const s=getComputedStyle(el),r=el.getBoundingClientRect();return s.display!=='none'&&s.visibility==='visible'&&Number(s.opacity)!==0&&r.width>0&&r.height>0;};
            const nodes=[...root.querySelectorAll(selector)];
            const title=root.getAttribute('aria-label')||root.querySelector('h1,h2,[role="heading"]')?.innerText||'';
            const scrollable=[root,...root.querySelectorAll('*')].some(el=>visible(el)&&el.scrollHeight>el.clientHeight+2&&/(auto|scroll)/.test(getComputedStyle(el).overflowY));
            return {title:title.slice(0,160),text_preview:root.innerText.slice(0,400),scrollable,buttons:nodes.flatMap((el,index)=>visible(el)?[{index,label:(el.getAttribute('aria-label')||el.innerText||el.value||el.title||'').trim().slice(0,160),text:(el.innerText||el.value||'').trim().slice(0,160),enabled:!el.disabled&&el.getAttribute('aria-disabled')!=='true'}]:[])};
        }''',CONTROLS)
        for button in info['buttons']:
            actions={classify(button['label']),classify(button['text'])}-{None}
            button['action']=next(iter(actions)) if len(actions)==1 else None
        return info

    async def inspect(self):
        root,error=await self._find()
        if error:
            return error
        try:
            return {'status':'popup_found',**await self._describe(root)}
        finally:
            await root.dispose()

    async def _scroll_root(self,root,direction,pixels):
        res=await root.evaluate('''(root,args)=>{
            const visible=el=>{const r=el.getBoundingClientRect(),s=getComputedStyle(el);return r.width>0&&r.height>0&&s.display!=='none'&&s.visibility==='visible'&&r.bottom>0&&r.top<innerHeight;};
            let nodes=[root,...root.querySelectorAll('*')].filter(el=>visible(el)&&el.scrollHeight>el.clientHeight+2&&/(auto|scroll)/.test(getComputedStyle(el).overflowY));
            nodes.sort((a,b)=>(b.clientWidth*b.clientHeight)-(a.clientWidth*a.clientHeight));
            const el=nodes.includes(root)?root:nodes[0];
            if(!el) return {moved:false,at_end:true,position:0};
            const r=el.getBoundingClientRect();
            const vx=Math.round(Math.max(0,Math.min(innerWidth-1,r.x+r.width/2))),vy=Math.round(Math.max(0,Math.min(innerHeight-1,r.y+r.height/2)));
            const bx=Math.max(0,Math.round((window.outerWidth-window.innerWidth)/2)),by=Math.max(0,Math.round(window.outerHeight-window.innerHeight-bx));
            const sx=Math.round((window.mozInnerScreenX!==undefined?window.mozInnerScreenX:window.screenX+bx)+vx);
            const sy=Math.round((window.mozInnerScreenY!==undefined?window.mozInnerScreenY:window.screenY+by)+vy);
            const before=el.scrollTop;
            el.scrollBy({top:args[0]==='down'?args[1]:-args[1],behavior:'instant'});
            return {moved:Math.abs(el.scrollTop-before)>0.5,position:Math.round(el.scrollTop),at_end:args[0]==='down'?el.scrollTop+el.clientHeight>=el.scrollHeight-2:el.scrollTop<=0,_point:[vx,vy],_screen:[sx,sy]};
        }''',[direction,pixels])
        pt=res.pop('_point',None)
        sc=res.pop('_screen',None)
        if pt and hasattr(self.browser,'_sync_pointer'):
            await self.browser._sync_pointer(pt,sc)
        return res

    async def scroll(self,direction='down',pixels=600,container='auto'):
        if direction not in {'down','up'} or container not in {'auto','page','popup'} or not 1<=pixels<=5000:
            raise ValueError('Invalid scroll direction, pixels or container')
        await self.browser.start()
        blocked=self.browser.block_status()
        if blocked:
            return blocked
        if container!='page':
            root,error=await self._find()
            if root:
                try:
                    return {'status':'ok','container':'popup',**await self._scroll_root(root,direction,pixels)}
                finally:
                    await root.dispose()
            if container=='popup' or error['status']=='ambiguous_popup':
                return error
        result=await self.browser.page.evaluate('''args=>{
            const el=document.scrollingElement,before=el.scrollTop;
            const vx=Math.round(innerWidth/2),vy=Math.round(innerHeight/2);
            const bx=Math.max(0,Math.round((window.outerWidth-window.innerWidth)/2)),by=Math.max(0,Math.round(window.outerHeight-window.innerHeight-bx));
            const sx=Math.round((window.mozInnerScreenX!==undefined?window.mozInnerScreenX:window.screenX+bx)+vx);
            const sy=Math.round((window.mozInnerScreenY!==undefined?window.mozInnerScreenY:window.screenY+by)+vy);
            el.scrollBy({top:args[0]==='down'?args[1]:-args[1],behavior:'instant'});
            return {moved:Math.abs(el.scrollTop-before)>0.5,position:Math.round(el.scrollTop),at_end:args[0]==='down'?el.scrollTop+el.clientHeight>=el.scrollHeight-2:el.scrollTop<=0,_point:[vx,vy],_screen:[sx,sy]};
        }''',[direction,pixels])
        pt=result.pop('_point',None)
        sc=result.pop('_screen',None)
        if pt and hasattr(self.browser,'_sync_pointer'):
            await self.browser._sync_pointer(pt,sc)
        return {'status':'ok','container':'page',**result}

    async def handle(self,action='inspect',max_scrolls=8):
        from playwright.async_api import Error
        if action not in {'inspect','accept','reject','dismiss'} or not 0<=max_scrolls<=20:
            raise ValueError('Invalid popup action or max_scrolls')
        await self.browser.start()
        blocked=self.browser.block_status()
        if blocked:
            return blocked
        if action=='inspect':
            return await self.inspect()
        root,error=await self._find()
        if error:
            return error
        try:
            for step in range(max_scrolls+1):
                info=await self._describe(root)
                matches=[b for b in info['buttons'] if b['action']==action]
                if len(matches)>1:
                    return {'status':'ambiguous_action','action':action,'buttons':info['buttons']}
                if not matches:
                    return {'status':'action_unavailable','action':action,'buttons':info['buttons']}
                chosen=matches[0]
                if chosen['enabled']:
                    controls=await root.query_selector_all(CONTROLS)
                    try:
                        if chosen['index']>=len(controls):
                            return {'status':'stale_target'}
                        button=controls[chosen['index']]
                        current=await button.evaluate('''el=>{
                            const r=el.getBoundingClientRect();
                            let vx=Math.round(r.x+r.width/2),vy=Math.round(r.y+r.height/2);
                            try {
                                let w=window;
                                while(w!==w.parent && w.frameElement){
                                    const fr=w.frameElement.getBoundingClientRect();
                                    vx+=Math.round(fr.x);vy+=Math.round(fr.y);
                                    w=w.parent;
                                }
                            } catch(e) {}
                            const bx=Math.max(0,Math.round((window.outerWidth-window.innerWidth)/2)),by=Math.max(0,Math.round(window.outerHeight-window.innerHeight-bx));
                            const sx=Math.round((window.mozInnerScreenX!==undefined?window.mozInnerScreenX:window.screenX+bx)+vx);
                            const sy=Math.round((window.mozInnerScreenY!==undefined?window.mozInnerScreenY:window.screenY+by)+vy);
                            return {
                                label:(el.getAttribute('aria-label')||el.innerText||el.value||el.title||'').trim().slice(0,160),
                                text:(el.innerText||el.value||'').trim().slice(0,160),
                                point:[vx,vy],
                                screen:[sx,sy]
                            };
                        }''')
                        pt=current.pop('point',None)
                        sc=current.pop('screen',None)
                        if current!={'label':chosen['label'],'text':chosen['text']} or not await button.is_enabled():
                            return {'status':'stale_target'}
                        if pt and hasattr(self.browser,'_sync_pointer'):
                            await self.browser._sync_pointer(pt,sc)
                        # Playwright scrolls this exact button's ancestors and checks
                        # visibility/occlusion. Never force-click or use guessed coordinates.
                        await button.click(timeout=2000,no_wait_after=True)
                    finally:
                        for control in controls:
                            await control.dispose()
                    try:
                        if not await root.is_visible():
                            closed=True
                        else:
                            await root.wait_for_element_state('hidden',timeout=250)
                            closed=True
                    except Error:
                        try:
                            closed=not await root.is_visible()
                        except Error:
                            closed=None
                    return {'status':'handled' if closed else 'action_sent','action':action,'button':chosen['label'],'popup_closed':closed,'scrolls':step}
                if step==max_scrolls:
                    return {'status':'scroll_limit','action':action,'scrolls':step,'button_enabled':False}
                moved=await self._scroll_root(root,'down',500)
                if not moved['moved']:
                    return {'status':'action_disabled','action':action,'scrolls':step}
                await asyncio.sleep(.01)
        except Error:
            return {'status':'stale_or_blocked_popup','action':action}
        finally:
            await root.dispose()
