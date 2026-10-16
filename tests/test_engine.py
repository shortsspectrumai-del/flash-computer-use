import asyncio
import base64
import json

import httpx
import pytest
from PIL import Image

from d1_computer_use_mcp.d1_engine import Settings, D1Engine, DecisionError


def test_settings_ollama(monkeypatch):
    monkeypatch.setenv('D1_PROVIDER', 'ollama')
    monkeypatch.setenv('D1_MODEL_NAME', 'custom-d1:latest')
    monkeypatch.setenv('D1_OLLAMA_BASE_URL', 'http://localhost:11434/')
    config = Settings.from_env()
    assert config.model == 'custom-d1:latest'
    assert config.base_url == 'http://localhost:11434'
    assert config.api_key == ''


def test_invalid_provider(monkeypatch):
    monkeypatch.setenv('D1_PROVIDER', 'typo')
    with pytest.raises(ValueError):
        Settings.from_env()


@pytest.mark.asyncio
async def test_ollama_image_choice_and_connection_reuse():
    requests = []
    def respond(request):
        requests.append(request)
        if request.url.path == '/api/show':
            return httpx.Response(200, json={'capabilities': ['vision', 'decision']})
        body = json.loads(request.content)
        assert body['model'] == 'test:latest'
        assert request.url.path == '/v1/systemone'
        assert body['keep_alive'] == '10m'
        assert list(body['questions']['pick']['criteria']) == ['1', '2']
        assert base64.b64decode(body['images'][0]).startswith(b'\x89PNG')
        return httpx.Response(200, json={'answers': {'pick': {'choice': '2', 'confidence': .9}}})
    client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    engine = D1Engine(Settings(provider='ollama', model='test:latest'), client=client)
    for _ in range(2):
        answer = await engine.ask_choice(Image.new('RGB', (20,20)), 'Login?', {'1':'Cancel','2':'Login'})
        assert answer['choice'] == '2'
        assert answer['confidence_source'] == 'calibrated_d1'
    assert [r.url.path for r in requests] == ['/api/show', '/v1/systemone', '/v1/systemone']
    await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize('bad', [{'choice':'999','confidence':.9}, {'choice':'1','confidence':1.1}, {'choice':'1','confidence':'0.9'}])
async def test_reject_invalid_answers(bad):
    def respond(request):
        if request.url.path == '/api/show':
            return httpx.Response(200, json={'capabilities':['vision','decision']})
        return httpx.Response(200, json={'answers':{'pick':bad}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        engine = D1Engine(Settings(provider='ollama', model='test'), client=client)
        with pytest.raises(DecisionError):
            await engine.ask_choice(Image.new('RGB',(10,10)), 'Pick', {'1':'Login'})


@pytest.mark.asyncio
async def test_no_vision_fails_before_inference():
    def respond(request):
        assert request.url.path == '/api/show'
        return httpx.Response(200, json={'capabilities':['completion']})
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        engine = D1Engine(Settings(provider='ollama', model='text'), client=client)
        with pytest.raises(DecisionError, match='vision'):
            await engine.ask_yes_no(Image.new('RGB',(10,10)), 'Ready?')


@pytest.mark.asyncio
async def test_api_uses_typed_decision_endpoint():
    def respond(request):
        assert request.url.path == '/v1/systemone'
        assert request.headers['authorization'] == 'Bearer secret'
        assert json.loads(request.content)['questions']['ready']['type'] == 'noul'
        return httpx.Response(200, json={'answers': {'ready': {'noul': .8}}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        engine = D1Engine(Settings(provider='api', model='LiquidAI/d1-3B', base_url='https://example.test/v1', api_key='secret'), client=client)
        result = await engine.evaluate(Image.new('RGB',(10,10)), {'ready': {'type':'noul','instructions':'Ready?'}})
        assert result['ready']['noul'] == .8
        assert result['ready']['confidence_source'] == 'provider'


@pytest.mark.asyncio
async def test_score_rebases_zero_based_levels():
    def respond(request):
        if request.url.path == '/api/show':
            return httpx.Response(200,json={'capabilities':['vision','decision']})
        return httpx.Response(200,json={'answers':{'rating':{'score':1.5,'confidence':.7}}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        engine = D1Engine(Settings(provider='ollama',model='d1:3b'),client=client)
        result = await engine.ask_score(Image.new('RGB',(10,10)), 'Rate', 3, 5)
        assert result['score'] == 4.5


@pytest.mark.asyncio
async def test_old_ollama_endpoint_fails_clearly():
    def respond(request):
        if request.url.path == '/api/show':
            return httpx.Response(200,json={'capabilities':['vision','decision']})
        return httpx.Response(404,json={'error':'not found'})
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        engine = D1Engine(Settings(provider='ollama',model='d1:3b'),client=client)
        with pytest.raises(DecisionError,match='recent Ollama'):
            await engine.ask_yes_no(Image.new('RGB',(10,10)),'Ready?')


@pytest.mark.asyncio
async def test_chat_vision_model_rejected_before_inference():
    def respond(request):
        assert request.url.path == '/api/show'
        return httpx.Response(200,json={'capabilities':['vision','completion']})
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        engine = D1Engine(Settings(provider='ollama',model='chat-vision'),client=client)
        with pytest.raises(DecisionError,match='decision capability'):
            await engine.ask_yes_no(Image.new('RGB',(10,10)),'Ready?')


@pytest.mark.asyncio
async def test_large_images_are_bounded_before_inference():
    import io
    def respond(request):
        if request.url.path == '/api/show':
            return httpx.Response(200,json={'capabilities':['vision','decision']})
        image=Image.open(io.BytesIO(base64.b64decode(json.loads(request.content)['images'][0])))
        assert image.size==(768,480)
        return httpx.Response(200,json={'answers':{'answer':{'noul':.9}}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        engine=D1Engine(Settings(provider='ollama',model='d1:3b'),client=client)
        await engine.ask_yes_no(Image.new('RGB',(1280,800)),'Ready?')
