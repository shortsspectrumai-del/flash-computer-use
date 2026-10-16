import sys
from types import SimpleNamespace
import pytest
from PIL import Image
from d1_computer_use_mcp.backends import Desktop
from d1_computer_use_mcp.actions import ComputerUse
from d1_computer_use_mcp.d1_engine import Settings


@pytest.fixture
def mouse(monkeypatch):
    state={'position':(20,20),'clicks':[]}
    def move(x,y,duration=0):
        state['position']=(x,y)
    def click(*,clicks=1,interval=0,button='left'):
        state['clicks'].append((state['position'],button,clicks))
    monkeypatch.setitem(sys.modules,'pyautogui',SimpleNamespace(moveTo=move,position=lambda:state['position'],click=click))
    class Screens:
        monitors=[{'left':-100,'top':0,'width':900,'height':600},{'left':-100,'top':0,'width':100,'height':100},{'left':0,'top':0,'width':800,'height':600}]
        def __enter__(self): return self
        def __exit__(self,*args): pass
    monkeypatch.setitem(sys.modules,'mss',SimpleNamespace(mss=Screens))
    return state


@pytest.mark.asyncio
async def test_real_pointer_backend_moves_without_click(mouse):
    result=await Desktop().move(-50,40,.1)
    assert result['status']=='ok'
    assert result['moved_coordinates']==[-50,40]
    assert mouse['position']==(-50,40)
    assert mouse['clicks']==[]


@pytest.mark.asyncio
async def test_click_current_position_and_right_double_click(mouse):
    result=await Desktop().mouse_click(button='right',double_click=True)
    assert result['status']=='ok'
    assert mouse['clicks']==[((20,20),'right',2)]


@pytest.mark.asyncio
async def test_invalid_point_never_moves_or_clicks(mouse):
    with pytest.raises(ValueError):
        await Desktop().mouse_click(-50,300)
    assert mouse['position']==(20,20)
    assert not mouse['clicks']


@pytest.mark.asyncio
async def test_half_coordinate_is_rejected(mouse):
    with pytest.raises(ValueError):
        await Desktop().mouse_click(x=30)
    assert not mouse['clicks']


@pytest.mark.asyncio
async def test_smart_move_locates_without_clicking():
    class Engine:
        settings=Settings()
        async def ask_choice(self,*args):
            return {'choice':'A1','confidence':.95,'confidence_source':'calibrated_d1'}
    class Screen:
        async def capture(self): return Image.new('RGB',(256,256)),(0,0)
        async def move(self,x,y,duration=.01): return {'status':'ok','moved_coordinates':[x,y]}
        async def click(self,*args,**kwargs): raise AssertionError('smart_move must not click')
    result=await ComputerUse(Engine(),None,Screen()).smart_move('target','desktop')
    assert result['status']=='ok'
    assert result['moved_coordinates']==[8,8]


@pytest.mark.asyncio
async def test_browser_syncs_real_desktop_pointer(mouse, monkeypatch):
    from d1_computer_use_mcp.backends import Browser
    monkeypatch.setenv('D1_REAL_MOUSE', 'always')
    browser = Browser()
    v_moves = []
    class FakeMouse:
        async def move(self, x, y, steps=1):
            v_moves.append((x, y))
        async def click(self, x, y, **kwargs):
            pass
    class FakePage:
        mouse = FakeMouse()
        def is_closed(self): return False
        async def evaluate(self, script, arg=None):
            return {'width': 1280, 'height': 800, 'screen': [100 + arg[0], 80 + arg[1]]}
    browser.page = FakePage()
    monkeypatch.setattr(browser, 'start', lambda: __import__('asyncio').sleep(0))
    res = await browser.move(120, 50, duration=0.01)
    assert res['status'] == 'ok'
    assert len(v_moves) >= 4
    assert v_moves[-1] == (120, 50)
    assert mouse['position'] == (220, 130)


def test_human_path_curve_and_endpoint_precision():
    from d1_computer_use_mcp.drawing import human_path
    pts = human_path((10, 10), (310, 210), bounds=(0, 0, 500, 400))
    assert len(pts) >= 4
    assert pts[-1] == [310, 210]
    assert all(0 <= x < 500 and 0 <= y < 400 for x, y in pts)
    # Verify natural arc (intermediate point deviates slightly from exact straight line)
    deviations = [abs((x - 10) * 200 - (y - 10) * 300) for x, y in pts[:-1]]
    assert max(deviations) > 0
