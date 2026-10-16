"""Opt-in live Amazon search in a separate headless browser; no account actions."""
import asyncio
import json
import os
import time
from pathlib import Path
os.environ.update(D1_PROVIDER='ollama',D1_MODEL_NAME='d1:3b',D1_OLLAMA_BASE_URL='http://127.0.0.1:11435',D1_BROWSER_HEADLESS='true')
os.environ.pop('D1_BROWSER_CDP_URL',None)
os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH',str(Path(__file__).resolve().parents[1]/'.runtime/playwright'))
from d1_computer_use_mcp.actions import ComputerUse
from d1_computer_use_mcp.backends import Browser
from d1_computer_use_mcp.d1_engine import D1Engine

async def main():
    browser,engine=Browser(),D1Engine()
    report={}
    try:
        start=time.perf_counter()
        report['open']=await browser.open('https://www.amazon.com/')
        report['open_seconds']=round(time.perf_counter()-start,3)
        candidates=await browser.candidates()
        report['visible_input_labels']=[e['label'] for e in candidates if e['editable']]
        labels=[e['label'] for e in report['open'].get('input_fields',[]) if e['role']=='searchbox']
        target='"'+labels[0]+'"' if len(labels)==1 else 'top Amazon search bar (field "Search Amazon")'
        start=time.perf_counter()
        report['search']=await ComputerUse(engine,browser,None).smart_type(target,'professional hair clipper',True)
        report['search_seconds']=round(time.perf_counter()-start,3)
        try:
            if report['open']['status']=='blocked':
                raise RuntimeError('Site blocked')
            await browser.page.wait_for_url('**/s?**',timeout=10000)
        except Exception:
            pass
        if report['search']['status']=='ok':
            start=time.perf_counter()
            report['results_ready']=await ComputerUse(engine,browser,None).wait_until_ready(timeout_seconds=10)
            report['results_ready_seconds']=round(time.perf_counter()-start,3)
        report['final_url']=browser.page.url
        report['submitted']='/s?' in browser.page.url and 'clipper' in browser.page.url
        print(json.dumps(report,indent=2),flush=True)
        Path('benchmarks/amazon-after.json').write_text(json.dumps(report,indent=2)+'\n')
    finally:
        await browser.close()
        await engine.close()

asyncio.run(main())
