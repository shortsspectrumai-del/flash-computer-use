from pathlib import Path
import pytest
from d1_computer_use_mcp.backends import Browser


@pytest.fixture
async def browser(monkeypatch):
    monkeypatch.setenv('PLAYWRIGHT_BROWSERS_PATH',str(Path('.runtime/playwright').resolve()))
    monkeypatch.setenv('D1_BROWSER_HEADLESS','true')
    monkeypatch.delenv('D1_BROWSER_CDP_URL',raising=False)
    b=Browser()
    await b.start()
    yield b
    await b.close()


def dialog(content):
    return '<style>[role=dialog]{position:fixed;inset:50px;background:white;padding:20px;border:1px solid;z-index:10}</style><button onclick="window.wrong=true">Accetta tutto</button><section role="dialog" aria-label="Prima di continuare su YouTube">'+content+'</section>'


@pytest.mark.asyncio
async def test_inspect_never_accepts(browser):
    await browser.page.set_content(dialog('<button onclick="window.accepted=true">Accetta tutto</button><button>Rifiuta tutto</button>'))
    result=await browser.popups.handle()
    assert result['status']=='popup_found'
    assert {b['action'] for b in result['buttons']}=={'accept','reject'}
    assert await browser.page.evaluate('window.accepted !== true && window.wrong !== true')


@pytest.mark.asyncio
async def test_reject_targets_popup_not_page(browser):
    await browser.page.set_content(dialog('<button onclick="window.accepted=true">Accetta tutto</button><button onclick="window.rejected=true;this.closest(\'[role=dialog]\').remove()">Rifiuta tutto</button>'))
    result=await browser.popups.handle('reject')
    assert result['status']=='handled'
    assert result['popup_closed'] is True
    assert await browser.page.evaluate('window.rejected === true && window.accepted !== true && window.wrong !== true')


@pytest.mark.asyncio
async def test_terms_scroll_unlocks_accept_without_scrolling_page(browser):
    await browser.page.set_content(dialog('''<div style="height:130px;overflow:auto" id="terms" onscroll="if(this.scrollTop+this.clientHeight>=this.scrollHeight-2)document.querySelector('#accept').disabled=false"><p style="height:900px">Termini e condizioni</p></div><button id="accept" disabled onclick="window.accepted=true;this.closest('[role=dialog]').remove()">Accetto</button>'''))
    result=await browser.popups.handle('accept',max_scrolls=8)
    assert result['status']=='handled'
    assert result['scrolls']>0
    assert await browser.page.evaluate('window.accepted === true && window.scrollY === 0')


@pytest.mark.asyncio
async def test_missing_reject_does_not_fall_back_to_accept(browser):
    await browser.page.set_content(dialog('<button onclick="window.accepted=true">Accetta tutto</button>'))
    result=await browser.popups.handle('reject')
    assert result['status']=='action_unavailable'
    assert await browser.page.evaluate('window.accepted !== true')


@pytest.mark.asyncio
async def test_popup_inside_iframe(browser):
    await browser.page.set_content('<iframe style="width:800px;height:500px;border:0"></iframe>')
    await browser.page.frames[1].set_content(dialog('<button onclick="window.rejected=true;this.closest(\'[role=dialog]\').remove()">Reject all</button>'))
    result=await browser.popups.handle('reject')
    assert result['status']=='handled'
    assert await browser.page.frames[1].evaluate('window.rejected === true')


@pytest.mark.asyncio
async def test_auto_scroll_stays_inside_modal(browser):
    await browser.page.set_content(dialog('<div id="terms" style="height:120px;overflow:auto"><p style="height:1000px">Terms</p></div><button>Accept all</button>'))
    result=await browser.popups.scroll('down',300,'auto')
    assert result['container']=='popup'
    assert result['moved'] is True
    assert await browser.page.locator('#terms').evaluate('el=>el.scrollTop')>0
    assert await browser.page.evaluate('window.scrollY')==0


@pytest.mark.asyncio
async def test_duplicate_accept_buttons_are_ambiguous(browser):
    await browser.page.set_content(dialog('<button onclick="window.wrong=true">Accept all</button><button onclick="window.wrong=true">Accept all</button>'))
    result=await browser.popups.handle('accept')
    assert result['status']=='ambiguous_action'
    assert await browser.page.evaluate('window.wrong !== true')


def test_youtube_accessible_cookie_labels_are_recognized():
    from d1_computer_use_mcp.popups import classify
    assert classify("Rifiuta l'utilizzo dei cookie e di altri dati per le finalità descritte")=='reject'
    assert classify("Accetta l'utilizzo dei cookie e di altri dati per le finalità descritte")=='accept'


@pytest.mark.asyncio
async def test_visible_reject_label_with_long_accessible_name(browser):
    await browser.page.set_content(dialog('<button aria-label="Reject the use of cookies and other data for the purposes described" onclick="window.rejected=true;this.closest(\'[role=dialog]\').remove()">Reject all</button>'))
    result=await browser.popups.handle('reject')
    assert result['status']=='handled'
    assert await browser.page.evaluate('window.rejected === true')


@pytest.mark.asyncio
async def test_conflicting_accessible_and_visible_labels_are_not_clicked(browser):
    await browser.page.set_content(dialog('<button aria-label="Accetta tutto" onclick="window.wrong=true">Rifiuta tutto</button>'))
    result=await browser.popups.handle('accept')
    assert result['status']=='action_unavailable'
    assert await browser.page.evaluate('window.wrong !== true')
