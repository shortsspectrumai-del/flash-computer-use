import os
import asyncio
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@pytest.mark.asyncio
async def test_stdio_initialization_lists_compact_tools():
    params = StdioServerParameters(command=os.path.abspath('.venv/bin/python'),args=['-m','d1_computer_use_mcp.server'],env={**os.environ,'D1_PROVIDER':'ollama','D1_MODEL_NAME':'d1:3b'})
    async with stdio_client(params) as (read,write):
        async with ClientSession(read,write) as session:
            init = await asyncio.wait_for(session.initialize(),10)
            assert init.serverInfo.name == 'Flash computer use'
            result = await session.list_tools()
            assert {t.name for t in result.tools} == {'browser_open','smart_click','smart_type','scroll_until_visible','visual_assert','wait_until_ready','handle_popup','browser_scroll','mouse_move','mouse_click','mouse_drag','smart_move','desktop_inspect','draw_path','draw_shape'}
            result = await session.call_tool('browser_open', {'url':'invalid'})
            assert result.structuredContent['status'] == 'error'
            assert all(c.type == 'text' for c in result.content)
