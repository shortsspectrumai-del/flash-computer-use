"""Opt-in live test on a synthetic page. Does not control the user's browser."""
import asyncio
import json
import os
from pathlib import Path

os.environ.setdefault('D1_PROVIDER','ollama')
os.environ.setdefault('D1_MODEL_NAME','d1:3b')
os.environ.setdefault('D1_OLLAMA_BASE_URL','http://127.0.0.1:11435')
os.environ.setdefault('D1_TIMEOUT_SECONDS','120')
os.environ['D1_BROWSER_HEADLESS'] = 'true'
os.environ.pop('D1_BROWSER_CDP_URL',None)
os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH',str(Path(__file__).resolve().parents[1]/'.runtime/playwright'))

from d1_computer_use_mcp.actions import ComputerUse
from d1_computer_use_mcp.backends import Browser
from d1_computer_use_mcp.d1_engine import D1Engine


async def main():
    engine, browser = D1Engine(), Browser()
    try:
        await browser.start()
        await browser.page.set_viewport_size({'width':640,'height':360})
        await browser.page.set_content('''<style>body{font:24px Arial;padding:40px;background:white}button{font:24px Arial;padding:20px;margin:10px}</style>
        <h1>Test page</h1><button onclick="document.querySelector('h1').textContent='Login completed'">Login</button><button>Cancel</button>''')
        result = await ComputerUse(engine,browser,None).smart_click('the Login button')
        result['verified_login'] = await browser.page.locator('h1').inner_text()=='Login completed'
        print(json.dumps(result,indent=2))
        assert result['verified_login'], result
    finally:
        await browser.close()
        await engine.close()


asyncio.run(main())
