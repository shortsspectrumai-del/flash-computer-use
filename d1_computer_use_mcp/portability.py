"""Portable configuration and explicit desktop prerequisites."""
import argparse
import importlib.util
import json
import os
import platform
import sys
from pathlib import Path


def platform_info(system=None,environ=None):
    system=system or platform.system()
    env=os.environ if environ is None else environ
    wayland=system=='Linux' and (env.get('XDG_SESSION_TYPE')=='wayland' or bool(env.get('WAYLAND_DISPLAY')))
    supported=system in {'Windows','Darwin','Linux'} and not wayland
    return {'system':system,'desktop_supported':supported,'permission_required':system=='Darwin',
            'session':('wayland' if wayland else 'x11') if system=='Linux' else 'native',
            'note':'Use an X11 session for the physical desktop; browser automation remains available.' if wayland else
                   'Grant Accessibility and Screen Recording permissions to the Python/client process.' if system=='Darwin' else
                   'Requires an unlocked interactive desktop; protected/elevated windows may need matching privileges.'}


def mcp_config(python=None,ollama_url='http://localhost:11434',use_npx=False):
    cmd='npx' if use_npx else (python or sys.executable)
    args=['-y','github:shortsspectrumai-del/flash-computer-use'] if use_npx else ['-m','d1_computer_use_mcp.server']
    return {'mcpServers':{'Flash computer use':{'command':cmd,'args':args,
            'env':{'D1_PROVIDER':'ollama','D1_MODEL_NAME':'d1:3b','D1_OLLAMA_BASE_URL':ollama_url,
                   'D1_BROWSER_STRATEGY':'hybrid','D1_DESKTOP_STRATEGY':'hybrid','D1_IMAGE_MAX_SIDE':'768'}}}}


def configure():
    parser=argparse.ArgumentParser(description='Generate portable MCP JSON for this Python environment or npx')
    parser.add_argument('--ollama-url',default='http://localhost:11434')
    parser.add_argument('--npx',action='store_true',help='Generate npx-based MCP configuration')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    text=json.dumps(mcp_config(ollama_url=args.ollama_url,use_npx=args.npx),indent=2)+'\n'
    if args.output:
        args.output.write_text(text)
    else:
        print(text,end='')


def doctor():
    result=platform_info()
    result['python']=sys.executable
    result['dependencies']={m:importlib.util.find_spec(m) is not None for m in ['mss','pyautogui','playwright','httpx']}
    result['ollama_url']=os.getenv('D1_OLLAMA_BASE_URL','http://localhost:11434')
    result['accessibility_backend']={'Linux':'AT-SPI, optional system Python bridge','Windows':'UI Automation, optional pywinauto','Darwin':'AX, optional PyObjC'}.get(result['system'],'unsupported')
    print(json.dumps(result,indent=2))
