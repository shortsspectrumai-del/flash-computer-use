"""Read-only D1 localization benchmark on a synthetic desktop image."""
import asyncio,json,os,time
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from d1_computer_use_mcp.d1_engine import D1Engine,Settings
from d1_computer_use_mcp.actions import ComputerUse

image=Image.new('RGB',(1920,1080),'#eeeeee')
draw=ImageDraw.Draw(image)
draw.rectangle((40,70,1850,1020),fill='white',outline='gray',width=2)
draw.text((60,90),'Drawing application',fill='black',font=ImageFont.load_default(size=28))
draw.rectangle((1490,320,1570,352),fill='#1269d3')
draw.text((1510,325),'Save',fill='white',font=ImageFont.load_default(size=18))

class Screen:
    async def capture(self): return image,(0,0)

async def main():
    reports=[]
    for depth in [2,3]:
        engine=D1Engine(Settings(provider='ollama',model='d1:3b',base_url=os.getenv('D1_OLLAMA_BASE_URL','http://127.0.0.1:11435'),desktop_strategy='vision',desktop_grid_depth=depth,timeout=120))
        try:
            start=time.perf_counter()
            result,_=await ComputerUse(engine,None,Screen()).locate('the small blue Save button towards the right','desktop')
            point=result.get('clicked_coordinates')
            inside=point is not None and 1490<=point[0]<=1570 and 320<=point[1]<=352
            report={'depth':depth,'seconds':round(time.perf_counter()-start,3),'inside_button':inside,'result':result}
            reports.append(report)
            print(json.dumps(report),flush=True)
        finally: await engine.close()
    Path('benchmarks/desktop-precision.json').write_text(json.dumps(reports,indent=2)+'\n')

asyncio.run(main())
