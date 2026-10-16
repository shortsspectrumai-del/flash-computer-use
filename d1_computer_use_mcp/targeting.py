"""Conservative DOM matching: ambiguous targets always fall back to vision."""
import re
import unicodedata


STOPWORDS = {'in','su','di','del','dello','della','dei','degli','delle','a','da','per','con','on','for','the','at','of','to'}
SEARCH_BAR_TERMS = (
    'search','search field','search box','search bar','search input',
    'campo di ricerca','barra di ricerca','campo ricerca','barra ricerca','casella di ricerca',
)


def normalize(text):
    return ' '.join(re.findall(r'\w+',unicodedata.normalize('NFKC',text).casefold()))


def _strip_stopwords(text):
    tokens=[t for t in text.split() if t not in STOPWORDS]
    return ' '.join(tokens) if tokens else text


def match_dom_target(target,elements):
    query=normalize(target)
    query_core=_strip_stopwords(query)
    quoted=[normalize(s) for s in re.findall(r'["“«]([^"”»]+)["”»]',target)]
    quoted_cores=[_strip_stopwords(q) for q in quoted if q]
    matches=[]
    for element in elements:
        aliases={normalize(a) for a in element.get('aliases',[element['label']]) if a}
        alias_cores={_strip_stopwords(a) for a in aliases if a}
        exact=query in aliases or (len(query_core)>=4 and query_core in alias_cores)
        # A quoted accessible label can omit a domain suffix or preposition, e.g. "Cerca in Amazon" vs "Cerca Amazon.it".
        named=any(
            a==q or (len(q)>=6 and a.startswith(q+' '))
            for q in quoted for a in aliases
        ) or any(
            ac==qc or (len(qc)>=6 and ac.startswith(qc+' '))
            for qc in quoted_cores for ac in alias_cores
        )
        if exact or named:
            matches.append(element)
    if matches:
        return matches[0] if len(matches)==1 else None
    # Generic search-bar requests may use a unique searchbox role; specific content queries (e.g. "cerca recensioni") may not.
    is_search_bar_query=(
        query in SEARCH_BAR_TERMS
        or any(query.startswith(term+' ') for term in SEARCH_BAR_TERMS if term!='search')
    )
    if is_search_bar_query:
        matches=[e for e in elements if e.get('role')=='searchbox']
        return matches[0] if len(matches)==1 else None
    return None


def crop_candidates(image,elements,padding=48):
    if not elements:
        return image
    boxes=[e['box'] for e in elements]
    left=max(0,int(min(b[0] for b in boxes))-padding)
    top=max(0,int(min(b[1] for b in boxes))-padding)
    right=min(image.width,int(max(b[0]+b[2] for b in boxes))+padding)
    bottom=min(image.height,int(max(b[1]+b[3] for b in boxes))+padding)
    return image.crop((left,top,right,bottom))
