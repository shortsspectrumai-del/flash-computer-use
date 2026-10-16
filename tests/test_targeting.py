from d1_computer_use_mcp.targeting import match_dom_target, crop_candidates
from PIL import Image


def candidate(id, label, **extra):
    return {'id':id,'label':label,'aliases':[label],'box':(10,10,120,30),**extra}


def test_quoted_search_label_matches_without_guessing():
    field=candidate('1','Cerca in Amazon.it',editable=True,role='searchbox')
    assert match_dom_target('barra di ricerca in alto (campo "Cerca in Amazon")',[field,candidate('2','Carrello')])==field


def test_duplicate_labels_are_ambiguous():
    assert match_dom_target('Login',[candidate('1','Login'),candidate('2','Login')]) is None


def test_specific_search_request_does_not_pick_unrelated_search():
    assert match_dom_target('cerca recensioni',[candidate('1','Cerca prodotti',role='searchbox')]) is None


def test_generic_search_field_can_use_unique_search_role():
    field=candidate('1','Search Amazon',role='searchbox',editable=True)
    assert match_dom_target('barra di ricerca',[field,candidate('2','Email',editable=True)])==field


def test_crop_keeps_target_badge_and_context():
    result=crop_candidates(Image.new('RGB',(1280,800)),[candidate('1','Search',box=(200,80,300,40))])
    assert result.width<1280 and result.height<800


def test_quoted_label_matches_when_site_omits_preposition():
    field=candidate('1','Cerca Amazon.it',editable=True,role='searchbox')
    assert match_dom_target('barra di ricerca di Amazon in alto (campo "Cerca in Amazon")',[field,candidate('2','Carrello')])==field
