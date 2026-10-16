import pytest
from PIL import Image
from d1_computer_use_mcp.actions import ComputerUse
from d1_computer_use_mcp.d1_engine import Settings


class FakeEngine:
    settings = Settings(threshold=.65)
    def __init__(self, confidence):
        self.confidence = confidence
    async def ask_choice(self, image, question, options):
        return {'choice':'1','confidence':self.confidence,'confidence_source':'calibrated_d1'}
    async def ask_yes_no(self, image, question):
        return {'noul': .9, 'answer': True, 'confidence':.9}


class FakeBrowser:
    def __init__(self):
        self.clicks = []
    async def capture(self):
        return Image.new('RGB', (100,100)), (0,0)
    async def snapshot(self):
        return Image.new('RGB',(100,100)), [{'id':'1','label':'Login','box':(10,10,20,20)}]
    async def click(self, x, y, double=False):
        self.clicks.append((x,y,double))


@pytest.mark.asyncio
async def test_low_confidence_does_not_click():
    browser = FakeBrowser()
    result = await ComputerUse(FakeEngine(.4), browser, None).smart_click('Login')
    assert result['status'] == 'low_confidence'
    assert browser.clicks == []


@pytest.mark.asyncio
async def test_click_uses_candidate_center():
    browser = FakeBrowser()
    result = await ComputerUse(FakeEngine(.9), browser, None).smart_click('Login', double_click=True)
    assert browser.clicks == [(20,20,True)]
    assert result['clicked_coordinates'] == [20,20]
    assert result['ui_changed'] is False


@pytest.mark.asyncio
async def test_absent_target_does_not_click():
    class Absent(FakeEngine):
        async def ask_choice(self,*args):
            return {'choice':'none','confidence':.99,'confidence_source':'calibrated_d1'}
    browser = FakeBrowser()
    result = await ComputerUse(Absent(.99), browser, None).smart_click('Missing')
    assert result['status'] == 'low_confidence'
    assert not browser.clicks


@pytest.mark.asyncio
async def test_changing_ui_aborts_click():
    class ChangingBrowser(FakeBrowser):
        async def capture(self):
            return Image.new('RGB',(100,100),'white'),(0,0)
    browser = ChangingBrowser()
    result = await ComputerUse(FakeEngine(.9),browser,None).smart_click('Login')
    assert result['status'] == 'ui_changed_before_click'
    assert not browser.clicks


@pytest.mark.asyncio
async def test_scroll_stops_at_limit():
    class NeverVisible(FakeEngine):
        async def ask_yes_no(self,*args):
            return {'noul':.1,'answer':False,'confidence':.9}
    class ScrollBrowser(FakeBrowser):
        count = 0
        async def scroll(self,direction):
            self.count += 1
    browser = ScrollBrowser()
    result = await ComputerUse(NeverVisible(.9),browser,None).scroll_until_visible('Missing',max_scrolls=2)
    assert result['status'] == 'not_found'
    assert browser.count == 2


@pytest.mark.asyncio
async def test_wait_deadline_covers_inference():
    import asyncio
    class Slow(FakeEngine):
        async def ask_yes_no(self,*args):
            await asyncio.sleep(10)
    result = await ComputerUse(Slow(.9),FakeBrowser(),None).wait_until_ready(timeout_seconds=.01)
    assert result['status'] == 'timeout'


@pytest.mark.asyncio
async def test_weak_visual_probability_is_reported_as_uncertain():
    class Weak(FakeEngine):
        async def evaluate(self,image,questions):
            return {'0':{'noul':.55,'answer':True,'confidence':.55,'confidence_source':'calibrated_d1'}}
    result=await ComputerUse(Weak(.55),FakeBrowser(),None).visual_assert(['Has search succeeded?'])
    assert result['results'][0]['answer'] is None
    assert result['results'][0]['certain'] is False


@pytest.mark.asyncio
async def test_scroll_stops_when_popup_is_at_end():
    class NeverVisible(FakeEngine):
        calls=0
        async def ask_yes_no(self,*args):
            self.calls+=1
            return {'noul':.1,'answer':False,'confidence':.9}
    class EndBrowser(FakeBrowser):
        async def scroll(self,direction):
            return {'status':'ok','container':'popup','moved':False,'at_end':True}
    engine=NeverVisible(.9)
    result=await ComputerUse(engine,EndBrowser(),None).scroll_until_visible('Missing')
    assert result['status']=='not_found'
    assert result['at_end'] is True
    assert engine.calls==1
