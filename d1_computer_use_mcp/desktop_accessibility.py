import asyncio
import json
import os
import platform
import sys
import time
from pathlib import Path
from .targeting import match_dom_target


class Accessibility:
    def __init__(self):
        self.unavailable_until=0
        self._cached=None
        self._cached_at=0.0

    async def snapshot(self,max_age=0.12):
        now=time.monotonic()
        if now<self.unavailable_until:
            return {'available':False,'elements':[]}
        if max_age>0 and self._cached is not None and (now-self._cached_at)<=max_age:
            return self._cached
        python=os.getenv('D1_ACCESSIBILITY_PYTHON',sys.executable)
        if platform.system()=='Linux' and 'D1_ACCESSIBILITY_PYTHON' not in os.environ and Path('/usr/bin/python3').exists():
            python='/usr/bin/python3'
        process=None
        try:
            process=await asyncio.create_subprocess_exec(python,str(Path(__file__).with_name('native_accessibility.py')),stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL)
            stdout,_=await asyncio.wait_for(process.communicate(),timeout=1.0)
            result=json.loads(stdout)
            if not result.get('available'):
                self.unavailable_until=time.monotonic()+30
                self._cached=None
            else:
                self._cached=result
                self._cached_at=time.monotonic()
            return result
        except (OSError,ValueError,asyncio.TimeoutError):
            self.unavailable_until=time.monotonic()+30
            self._cached=None
            return {'available':False,'elements':[]}
        finally:
            if process and process.returncode is None:
                process.kill()
                await process.wait()

    async def target(self,description,editable_only=False):
        snapshot=await self.snapshot()
        elements=snapshot.get('elements',[])
        if editable_only:
            elements=[e for e in elements if e.get('editable')]
        return match_dom_target(description,elements)

    async def validate(self,target):
        snapshot=await self.snapshot(max_age=0.05)
        return any(all(current.get(key)==target.get(key) for key in ['id','label','box','window','editable']) for current in snapshot.get('elements',[]))
