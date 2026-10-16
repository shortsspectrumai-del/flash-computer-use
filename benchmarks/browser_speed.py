"""Opt-in benchmark: dedicated synthetic browser, real local D1, no user UI."""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('D1_PROVIDER','ollama')
os.environ.setdefault('D1_MODEL_NAME','d1:3b')
os.environ.setdefault('D1_OLLAMA_BASE_URL','http://127.0.0.1:11435')
os.environ.setdefault('D1_TIMEOUT_SECONDS','120')
os.environ['D1_BROWSER_HEADLESS']='true'
os.environ.pop('D1_BROWSER_CDP_URL',None)
os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH',str(ROOT/'.runtime/playwright'))

from d1_computer_use_mcp.actions import ComputerUse
from d1_computer_use_mcp.backends import Browser
from d1_computer_use_mcp.d1_engine import D1Engine

HTML = '''<style>body{margin:0;font:16px Arial;background:#eee}header{padding:18px;background:#131921;color:white;display:flex;gap:20px;align-items:center}input{font:18px Arial;padding:12px;width:550px}nav{background:#232f3e;padding:15px;display:flex;flex-wrap:wrap;gap:8px}nav a{color:white;padding:5px}main{padding:20px;display:grid;grid-template-columns:repeat(6,1fr);gap:12px}article{background:white;padding:12px;height:180px}button{padding:10px}</style>
<header><strong>Shop</strong><form onsubmit="event.preventDefault();document.querySelector('h2').textContent='Results: '+document.querySelector('input').value"><input type="search" aria-label="Cerca in Amazon" placeholder="Cerca in Amazon" name="field-keywords" id="twotabsearchtextbox"><button>Cerca</button></form><button>Accedi</button><button>Carrello</button></header>
<nav>''' + ''.join(f'<a href="#cat{i}">Categoria {i}</a>' for i in range(30)) + '''</nav><h2>Products</h2><main>''' + ''.join(f'<article>Prodotto {i}<p>€ 29.99</p><button>Dettagli {i}</button></article>' for i in range(18)) + '</main>'

class TimedEngine(D1Engine):
    def __init__(self):
        super().__init__()
        self.calls=[]
    async def evaluate(self,image,questions):
        start=time.perf_counter()
        try:
            return await super().evaluate(image,questions)
        finally:
            self.calls.append({'seconds':round(time.perf_counter()-start,3),'size':image.size,'questions':len(questions)})

async def main():
    engine, browser = TimedEngine(),Browser()
    report={'runs':[]}
    try:
        await browser.start()
        actions=ComputerUse(engine,browser,None)
        for _ in range(int(os.getenv('D1_BENCH_RUNS','1'))):
            await browser.page.set_content(HTML)
            engine.calls.clear()
            start=time.perf_counter()
            ready=await actions.wait_until_ready(timeout_seconds=40)
            ready_seconds=time.perf_counter()-start
            start=time.perf_counter()
            typed=await actions.smart_type('barra di ricerca di Amazon in alto (campo "Cerca in Amazon")','taglia capelli professionale',True)
            type_seconds=time.perf_counter()-start
            actual=await browser.page.locator('input').input_value()
            submitted=await browser.page.locator('h2').inner_text()
            result={'ready_seconds':round(ready_seconds,3),'type_seconds':round(type_seconds,3),'ready':ready,'type':typed,'correct':actual=='taglia capelli professionale' and submitted=='Results: taglia capelli professionale','inferences':list(engine.calls)}
            report['runs'].append(result)
            print(json.dumps(result),flush=True)
        if len(sys.argv)>1:
            Path(sys.argv[1]).write_text(json.dumps(report,indent=2)+'\n')
    finally:
        await browser.close()
        await engine.close()

asyncio.run(main())
