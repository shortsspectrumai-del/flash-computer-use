from d1_computer_use_mcp.targeting import (
    match_dom_target,
    crop_candidates,
    select_d1_candidates,
    format_d1_options,
)
from PIL import Image


def candidate(id, label, **extra):
    return {'id':id,'label':label,'aliases':[label],'box':(10,10,120,30),**extra}


def test_quoted_search_label_matches_without_guessing():
    field=candidate('1','Search in Amazon.com',editable=True,role='searchbox')
    assert match_dom_target('top search bar (field "Search in Amazon")',[field,candidate('2','Cart')])==field


def test_duplicate_labels_are_ambiguous():
    assert match_dom_target('Login',[candidate('1','Login'),candidate('2','Login')]) is None


def test_duplicate_labels_disambiguated_by_card_context():
    c1=candidate('1','Details',context='Product 1 $19.99',role='button')
    c2=candidate('2','Details',context='Product 2 $29.99',role='button')
    c3=candidate('3','Details',context='Product 3 $39.99',role='button')
    assert match_dom_target('Click Details for Product 2',[c1,c2,c3])==c2


def test_duplicate_labels_disambiguated_by_zone():
    top_btn=candidate('1','Sign in',zone='header top-right',role='button')
    bottom_btn=candidate('2','Sign in',zone='footer bottom',role='button')
    assert match_dom_target('Sign in button in the header',[top_btn,bottom_btn])==top_btn


def test_select_d1_candidates_narrows_dense_page_to_relevant_subset():
    elements=[candidate(str(i),f'Category {i}',role='link') for i in range(1,40)]
    b1=candidate('40','Add to Cart',context='Basic Plan',role='button')
    b2=candidate('41','Add to Cart',context='Pro Plan',role='button')
    elements.extend([b1,b2])
    narrowed=select_d1_candidates('Add to Cart button',elements)
    assert narrowed==[b1,b2]
    opts=format_d1_options(narrowed)
    assert 'Basic Plan' in opts['40']
    assert 'Pro Plan' in opts['41']


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
