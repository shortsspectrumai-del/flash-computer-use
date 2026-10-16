import pytest
from PIL import Image
from d1_computer_use_mcp.actions import ComputerUse
from d1_computer_use_mcp.d1_engine import Settings
from d1_computer_use_mcp.drawing import shape_points, validate_path
from d1_computer_use_mcp.portability import platform_info, mcp_config


def test_shapes_are_closed_and_bounded():
    for shape in ['rectangle','ellipse']:
        points=shape_points(shape,10,20,100,60)
        assert points[0]==points[-1]
        assert all(10<=x<=110 and 20<=y<=80 for x,y in points)
    assert shape_points('line',10,20,100,60)==[[10,20],[110,80]]


def test_drawing_requires_all_points_inside_canvas():
    with pytest.raises(ValueError):
        validate_path([[20,20],[200,20]],[0,0,100,100])


def test_platform_status_is_explicit_about_wayland():
    assert platform_info('Linux',{'XDG_SESSION_TYPE':'wayland'})['desktop_supported'] is False
    assert platform_info('Windows',{})['desktop_supported'] is True
    assert platform_info('Darwin',{})['permission_required'] is True


def test_generated_config_has_no_machine_specific_paths():
    config=mcp_config('/portable/venv/python','http://localhost:11434')
    entry=config['mcpServers']['Flash computer use']
    assert entry['command']=='/portable/venv/python'
    assert entry['args']==['-m','d1_computer_use_mcp.server']
    assert entry['env']['D1_OLLAMA_BASE_URL']=='http://localhost:11434'


@pytest.mark.asyncio
async def test_accessible_desktop_target_avoids_all_inference():
    class Engine:
        settings=Settings()
        async def ask_choice(self,*args): raise AssertionError('Must use accessibility')
    class Screen:
        async def accessible_target(self,*args):
            return {'id':'app/button','label':'Save','box':[10,20,60,30],'window':'app'}
        async def interact_accessible(self,target,hover=False,double=False):
            return {'status':'ok','moved_coordinates':[40,35]} if hover else {'status':'ok','clicked_coordinates':[40,35]}
        async def capture(self): raise AssertionError('Exact accessible targets do not need screenshots')
    result=await ComputerUse(Engine(),None,Screen()).smart_click('Save','desktop')
    assert result['status']=='ok'
    assert result['method']=='accessibility'


@pytest.mark.asyncio
async def test_grid_refines_large_screens_for_small_controls():
    class Engine:
        settings=Settings(desktop_grid_depth=3)
        calls=0
        async def ask_choice(self,*args):
            self.calls+=1
            return {'choice':'A1','confidence':.95,'confidence_source':'calibrated_d1'}
    class Screen:
        async def capture(self): return Image.new('RGB',(1920,1080)),(0,0)
    engine=Engine()
    result,_=await ComputerUse(engine,None,Screen()).locate('small button','desktop')
    assert engine.calls==3
    assert result['cell_size']==[30,16]
    assert result['clicked_coordinates']==[15,8]


@pytest.mark.asyncio
async def test_accessibility_revalidation_blocks_stale_target(monkeypatch):
    from d1_computer_use_mcp.backends import Desktop
    desktop=Desktop()
    async def invalid(target): return False
    monkeypatch.setattr(desktop.accessibility,'validate',invalid)
    async def wrong(*args,**kwargs): raise AssertionError('Must not click stale target')
    monkeypatch.setattr(desktop,'mouse_click',wrong)
    result=await desktop.interact_accessible({'box':[10,20,30,30]})
    assert result['status']=='stale_accessible_target'


@pytest.mark.asyncio
async def test_desktop_drawing_releases_mouse_after_error(monkeypatch):
    import sys
    from types import SimpleNamespace
    from d1_computer_use_mcp.backends import Desktop
    calls=[]
    def move(x,y,**kwargs):
        calls.append(('move',x,y))
        if x==40: raise RuntimeError('Interrupted stroke')
    fake=SimpleNamespace(moveTo=move,mouseDown=lambda **kwargs:calls.append(('down',)),mouseUp=lambda **kwargs:calls.append(('up',)),FAILSAFE=True)
    monkeypatch.setitem(sys.modules,'pyautogui',fake)
    monkeypatch.setattr(Desktop,'_validate_points',staticmethod(lambda points:None))
    with pytest.raises(RuntimeError):
        await Desktop().draw_path([[20,20],[40,40]],[0,0,100,100],0)
    assert calls[-1]==('up',)
    assert fake.FAILSAFE is True


@pytest.mark.asyncio
async def test_macos_secondary_retina_monitor_scales_to_logical_bounds(monkeypatch):
    import sys, platform
    from types import SimpleNamespace
    from d1_computer_use_mcp.backends import Desktop
    monkeypatch.setattr(platform,'system',lambda:'Darwin')
    monkeypatch.setenv('D1_MONITOR','2')
    class Shot:
        size=(400,200)
        rgb=b'\x00'*(400*200*3)
    class Screens:
        monitors=[
            {'left':-200,'top':0,'width':400,'height':100},
            {'left':0,'top':0,'width':200,'height':100},
            {'left':-200,'top':0,'width':200,'height':100},
        ]
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def grab(self,m): return Shot()
    monkeypatch.setitem(sys.modules,'mss',SimpleNamespace(mss=Screens))
    image,origin=await Desktop().capture()
    assert image.size==(200,100)
    assert origin==(-200,0)


@pytest.mark.asyncio
async def test_desktop_type_falls_back_when_clipboard_unavailable(monkeypatch):
    import sys
    from types import SimpleNamespace
    from d1_computer_use_mcp.backends import Desktop
    events=[]
    fake_pg=SimpleNamespace(
        hotkey=lambda *a:events.append(('hotkey',a)),
        write=lambda text,interval=0:events.append(('write',text)),
        press=lambda k:events.append(('press',k)),
        PAUSE=0.1,
    )
    fake_clip=SimpleNamespace(paste=lambda:(_ for _ in ()).throw(RuntimeError('no clipboard')))
    monkeypatch.setitem(sys.modules,'pyautogui',fake_pg)
    monkeypatch.setitem(sys.modules,'pyperclip',fake_clip)
    await Desktop().type('hello',enter=True,replace=True)
    assert ('write','hello') in events
    assert ('press','enter') in events
    assert fake_pg.PAUSE==0


def test_extended_paint_shapes_and_visual_canvas_sheet_detection():
    from PIL import ImageDraw
    from d1_computer_use_mcp.drawing import SHAPES, detect_canvas_from_image
    for shape in SHAPES:
        pts=shape_points(shape,20,30,120,80)
        assert len(pts)>=2
        assert all(20<=x<=140 and 30<=y<=110 for x,y in pts)
    # Simulate a Paint window: dark gray UI chrome with a white 500x350 canvas sheet at (100, 120)
    img=Image.new('RGB',(800,600),(60,60,60))
    ImageDraw.Draw(img).rectangle((100,120,600,470),fill=(255,255,255))
    bounds=detect_canvas_from_image(img,origin=(10,20))
    assert 100<=bounds[0]<=130 and 130<=bounds[1]<=160
    assert 440<=bounds[2]<=510 and 300<=bounds[3]<=360


@pytest.mark.asyncio
async def test_multi_stroke_drawing_and_mouse_drag(monkeypatch):
    import sys
    from types import SimpleNamespace
    from d1_computer_use_mcp.backends import Desktop
    events=[]
    fake=SimpleNamespace(
        position=lambda:(10,10),
        moveTo=lambda x,y,**kw:events.append(('move',x,y)),
        mouseDown=lambda **kw:events.append(('down',)),
        mouseUp=lambda **kw:events.append(('up',)),
        FAILSAFE=True,
    )
    monkeypatch.setitem(sys.modules,'pyautogui',fake)
    monkeypatch.setattr(Desktop,'_validate_points',staticmethod(lambda pts:None))
    desktop=Desktop()
    res=await desktop.draw_path([[[10,10],[30,10]],[[50,50],[70,70]]],[0,0,100,100],0)
    assert res['status']=='ok'
    assert res['strokes_drawn']==2
    assert res['points_drawn']==4
    assert events.count(('down',))==2 and events.count(('up',))==2
    events.clear()
    drag_res=await desktop.mouse_drag(15,20,45,60,duration=0)
    assert drag_res['status']=='ok'
    assert ('down',) in events and events[-1]==('up',)
