import asyncio
from PIL import ImageChops, ImageStat
from .som_annotator import annotate
from .vision_grid import grid
from .targeting import match_dom_target, crop_candidates


class ComputerUse:
    def __init__(self, engine, browser, desktop):
        self.engine, self.browser, self.desktop = engine, browser, desktop

    def backend(self, mode):
        if mode not in {'browser','desktop'}:
            raise ValueError('mode must be browser or desktop')
        return self.browser if mode == 'browser' else self.desktop

    async def _choose(self, image, target, options):
        # System One accepts at most 26 choices. Reserve one for absent targets.
        options = {**options, 'none': 'Target is absent or cannot be identified clearly'}
        return await self.engine.ask_choice(image, f'Find the target: {target}. Choose none if absent.', options)

    async def locate(self,target,mode,editable_only=False):
        backend = self.backend(mode)
        threshold = self.engine.settings.threshold
        if mode=='browser' and hasattr(backend,'block_status') and backend.block_status():
            return backend.block_status(),None
        if mode=='desktop' and self.engine.settings.desktop_strategy=='hybrid' and hasattr(backend,'accessible_target'):
            accessible=await backend.accessible_target(target,editable_only)
            if accessible is not None:
                x,y,w,h=accessible['box']
                return {'status':'ok','_accessible_target':accessible,'clicked_coordinates':[round(x+w/2),round(y+h/2)],
                        'method':'accessibility','confidence':1.,'confidence_source':'accessibility_unique_match'},None
        if mode == 'browser':
            if hasattr(backend,'candidates'):
                elements=await backend.candidates()
                if editable_only:
                    elements=[e for e in elements if e.get('editable')]
                if self.engine.settings.browser_strategy=='hybrid':
                    exact=match_dom_target(target,elements)
                    if exact is not None:
                        x,y,w,h=exact['box']
                        return {'status':'ok','candidate_id':exact['id'],
                                'clicked_coordinates':[round(x+w/2),round(y+h/2)],
                                'confidence':1.,'confidence_source':'dom_unique_match','method':'dom'},None
                before,_=await backend.capture()
            else:
                before,elements=await backend.snapshot()
            if not elements:
                return {'status':'not_found'}, before
            image = annotate(before,elements)
            if editable_only:
                image=crop_candidates(image,elements)
            candidates = elements
            group_confidence = 1.
            if len(elements)>25:
                groups = [elements[i:i+25] for i in range(0,len(elements),25)]
                choice = await self._choose(image,target,{str(i): '; '.join(e['id']+': '+e['label'] for e in group) for i,group in enumerate(groups)})
                if choice['choice']=='none' or choice['confidence']<threshold:
                    return {'status':'low_confidence',**choice},before
                candidates = groups[int(choice['choice'])]
                group_confidence = choice['confidence']
            choice = await self._choose(image,target,{e['id']:e['label'] for e in candidates})
            if choice['choice']=='none' or choice['confidence']<threshold:
                return {'status':'low_confidence',**choice},before
            element = next(e for e in candidates if e['id']==choice['choice'])
            x,y,w,h = element['box']
            point = [round(x+w/2),round(y+h/2)]
            confidence = min(group_confidence,choice['confidence'])
        else:
            before,origin=await backend.capture()
            selected=(0,0,before.width,before.height)
            confidence=1.
            for depth in range(self.engine.settings.desktop_grid_depth):
                crop=before.crop(selected)
                image,cells=grid(crop,enlarge=True)
                choice=await self._choose(image,target,{key:f'Target center inside cell {key}' for key in cells})
                if choice['choice']=='none' or choice['confidence']<threshold:
                    return {'status':'low_confidence',**choice},before
                confidence=min(confidence,choice['confidence'])
                cell=cells[choice['choice']]
                selected=(selected[0]+cell[0],selected[1]+cell[1],selected[0]+cell[2],selected[1]+cell[3])
                if depth>=1 and max(selected[2]-selected[0],selected[3]-selected[1])<=24:
                    break
            point=[origin[0]+(selected[0]+selected[2])//2,origin[1]+(selected[1]+selected[3])//2]
        result={'status':'ok','clicked_coordinates':point,'confidence':confidence,
                'confidence_source':choice['confidence_source'],'method':'d1'}
        if mode=='browser' and hasattr(backend,'interact_candidate'):
            result['candidate_id']=element['id']
        if mode=='desktop':
            result['cell_size']=[selected[2]-selected[0],selected[3]-selected[1]]
            result['refinement_steps']=depth+1
        return result,before

    async def smart_click(self,target_description,mode='browser',double_click=False,editable_only=False):
        result,before = await self.locate(target_description,mode,editable_only)
        if result['status']!='ok':
            return result
        backend = self.backend(mode)
        if '_accessible_target' in result:
            target=result.pop('_accessible_target')
            return {**result,**await backend.interact_accessible(target,double=double_click)}
        if mode=='browser' and 'candidate_id' in result:
            return await self._interact_browser(result,before,double=double_click)
        current,_ = await backend.capture()
        if self.changed(before,current):
            return {**result,'status':'ui_changed_before_click'}
        outcome=await backend.click(*result['clicked_coordinates'],double=double_click)
        if isinstance(outcome,dict) and outcome['status']!='ok':
            return {**result,**outcome}
        await asyncio.sleep(.02)
        after,_ = await backend.capture()
        result['ui_changed'] = self.changed(before,after)
        return result

    async def smart_move(self,target_description,mode='desktop'):
        result,before=await self.locate(target_description,mode)
        if result['status']!='ok':
            return result
        backend=self.backend(mode)
        if '_accessible_target' in result:
            target=result.pop('_accessible_target')
            result.pop('clicked_coordinates',None)
            return {**result,**await backend.interact_accessible(target,hover=True)}
        if mode=='browser' and 'candidate_id' in result:
            result=await self._interact_browser(result,before,hover=True)
            if 'clicked_coordinates' in result:
                result['moved_coordinates']=result.pop('clicked_coordinates')
            return result
        current,_=await backend.capture()
        if self.changed(before,current):
            return {**result,'status':'ui_changed_before_move'}
        point=result.pop('clicked_coordinates')
        return {**result,**await backend.move(*point)}

    @staticmethod
    def changed(before,after):
        if before.size != after.size:
            return True
        b = before if before.mode == 'RGB' else before.convert('RGB')
        a = after if after.mode == 'RGB' else after.convert('RGB')
        if b.tobytes() == a.tobytes():
            return False
        delta = ImageChops.difference(b,a)
        return sum(ImageStat.Stat(delta).mean)/3 > 1.

    async def _interact_browser(self,result,before,**interaction):
        from playwright.async_api import Error as PlaywrightError
        candidate_id=result.pop('candidate_id')
        if before is None:
            try:
                before,_=await self.browser.capture()
            except PlaywrightError:
                pass
        previous_url=self.browser.page.url
        outcome=await self.browser.interact_candidate(candidate_id,**interaction)
        result.update(outcome)
        if result['status']=='ok':
            if self.browser.page.url!=previous_url:
                result['ui_changed']=True
            elif before is None:
                result.update(ui_changed=None,verification_pending=True)
            else:
                try:
                    after,_=await self.browser.capture()
                    result['ui_changed']=self.changed(before,after)
                except PlaywrightError:
                    # The action already succeeded. A navigation can interrupt
                    # screenshots; reporting an action failure would invite repeats.
                    result.update(ui_changed=None,verification_pending=True)
        else:
            result.pop('clicked_coordinates',None)
        return result

    async def smart_type(self,target_description,text_to_type,press_enter=True,mode='browser'):
        if mode=='browser' and hasattr(self.browser,'interact_candidate'):
            result,before=await self.locate(target_description,mode,editable_only=True)
            if result['status']!='ok':
                return result
            return await self._interact_browser(result,before,text=text_to_type,enter=press_enter)
        result=await self.smart_click(target_description,mode,editable_only=True)
        if result['status']=='ok':
            if mode=='desktop' and result.get('method')=='accessibility':
                await self.backend(mode).type(text_to_type,press_enter,replace=True)
            else:
                await self.backend(mode).type(text_to_type,press_enter)
            result['typed_characters']=len(text_to_type)
        return result

    async def visual_assert(self,questions,mode='browser'):
        if not 1 <= len(questions) <= 64:
            raise ValueError('Provide 1 to 64 questions')
        backend=self.backend(mode)
        if mode=='browser' and hasattr(backend,'block_status') and backend.block_status():
            return backend.block_status()
        image,_ = await backend.capture()
        answers = await self.engine.evaluate(image,{str(i):{'type':'noul','instructions':q} for i,q in enumerate(questions)})
        results=[]
        for i,q in enumerate(questions):
            answer=answers[str(i)]
            certain=answer['noul']<=.2 or answer['noul']>=.8
            results.append({'question':q,**answer,'answer':answer['answer'] if certain else None,'certain':certain})
        return {'status':'ok','results':results}

    async def scroll_until_visible(self,target_description,direction='down',max_scrolls=8,mode='browser'):
        if direction not in {'up','down'} or not 0<=max_scrolls<=100:
            raise ValueError('Invalid direction or max_scrolls')
        backend = self.backend(mode)
        for step in range(max_scrolls+1):
            if mode=='browser' and hasattr(backend,'block_status') and backend.block_status():
                return backend.block_status()
            image,_ = await backend.capture()
            answer = await self.engine.ask_yes_no(image,f'Is {target_description} clearly visible?')
            if answer['noul']>=.8:
                return {'status':'visible','scrolls':step,**answer}
            if step<max_scrolls:
                outcome=await backend.scroll(direction)
                if isinstance(outcome,dict):
                    if outcome['status']!='ok':
                        return outcome
                    if not outcome.get('moved',True):
                        return {'status':'not_found','scrolls':step+1,'at_end':True,**answer}
        return {'status':'not_found','scrolls':max_scrolls,**answer}

    async def wait_until_ready(self,timeout_seconds=10,mode='browser'):
        if not 0<timeout_seconds<=300:
            raise ValueError('Timeout must be 0..300 seconds')
        async def poll():
            while True:
                backend=self.backend(mode)
                if mode=='browser' and hasattr(backend,'block_status') and backend.block_status():
                    return backend.block_status()
                if mode=='browser' and self.engine.settings.browser_strategy=='hybrid' and hasattr(backend,'readiness'):
                    if await backend.readiness():
                        return {'status':'ready','method':'dom'}
                    await asyncio.sleep(.02)
                    continue
                image,_ = await backend.capture()
                answer = await self.engine.ask_yes_no(image,'Is this UI ready for interaction, with no loading spinner, skeleton screen or blank page?')
                if answer['noul']>=.8:
                    return {'status':'ready',**answer}
                await asyncio.sleep(.1)
        try:
            return await asyncio.wait_for(poll(),timeout=timeout_seconds)
        except asyncio.TimeoutError:
            return {'status':'timeout'}
