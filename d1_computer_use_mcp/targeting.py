"""Conservative DOM matching and D1 candidate ranking/cropping."""
import re
import unicodedata


STOPWORDS = {
    'in','su','di','del','dello','della','dei','degli','delle','a','da','per','con','il','lo','la','i','gli','le',
    'on','for','the','at','of','to','from','with','by','into','inside','within','button','pulsante','bottone',
    'link','field','campo','input','box','casella','bar','barra','click','clicca','press','premi',
}
SEARCH_BAR_TERMS = (
    'search','search field','search box','search bar','search input',
    'campo di ricerca','barra di ricerca','campo ricerca','barra ricerca','casella di ricerca',
)
ZONE_SYNONYMS = {
    'header': {'header','top','in alto','alto','navbar','top bar','barra in alto','intestazione'},
    'nav': {'nav','navbar','navigation','menu','barra di navigazione'},
    'footer': {'footer','bottom','in basso','basso','piè di pagina'},
    'aside': {'sidebar','aside','barra laterale','laterale'},
    'dialog': {'dialog','modal','popup','finestra','banner'},
    'top-left': {'top left','in alto a sinistra','alto a sinistra','upper left'},
    'top-right': {'top right','in alto a destra','alto a destra','upper right'},
    'bottom-left': {'bottom left','in basso a sinistra','basso a sinistra','lower left'},
    'bottom-right': {'bottom right','in basso a destra','basso a destra','lower right'},
    'left': {'left','sinistra','a sinistra'},
    'right': {'right','destra','a destra'},
}
ZONE_WORDS = {w for phrases in ZONE_SYNONYMS.values() for p in phrases for w in p.split()}
ROLE_SYNONYMS = {
    'searchbox': {'search','searchbox','search bar','search box','barra di ricerca','campo di ricerca','cerca'},
    'button': {'button','btn','pulsante','bottone'},
    'link': {'link','collegamento'},
    'textbox': {'input','field','textbox','text box','campo','casella'},
    'checkbox': {'checkbox','casella di spunta','spunta'},
    'combobox': {'select','dropdown','combobox','menu a tendina','tendina'},
}


def normalize(text):
    return ' '.join(re.findall(r'\w+',unicodedata.normalize('NFKC',str(text or '')).casefold()))


def _strip_stopwords(text):
    tokens=[t for t in text.split() if t not in STOPWORDS]
    return ' '.join(tokens) if tokens else text


def _query_zones(query_norm):
    q_tokens=set(query_norm.split())
    matched=set()
    for zone,phrases in ZONE_SYNONYMS.items():
        for p in phrases:
            p_tokens=p.split()
            if len(p_tokens)==1:
                if p_tokens[0] in q_tokens:
                    matched.add(zone)
            elif p in query_norm:
                matched.add(zone)
    return matched


def _element_matches_zone(element, requested_zones):
    if not requested_zones:
        return True
    el_zone=normalize(element.get('zone',''))
    if not el_zone:
        return False
    el_tokens=set(el_zone.split())
    for z in requested_zones:
        z_norm=normalize(z)
        if z_norm in el_zone or all(t in el_tokens for t in z_norm.split()):
            return True
    return False


def _disambiguate_by_context_or_zone(query_norm, candidates):
    """Disambiguate candidates sharing a matched label using container context or landmark/spatial zone."""
    requested_zones=_query_zones(query_norm)
    q_tokens=set(_strip_stopwords(query_norm).split())
    matched=[]
    for el, alias_used in candidates:
        alias_tokens=set(_strip_stopwords(alias_used).split())
        extra_tokens=q_tokens - alias_tokens - ZONE_WORDS
        if not extra_tokens and not requested_zones:
            continue
        zone_ok=_element_matches_zone(el, requested_zones)
        if requested_zones and not zone_ok:
            continue
        if extra_tokens:
            ctx_tokens=set(_strip_stopwords(normalize(el.get('context',''))).split())
            if not extra_tokens.issubset(ctx_tokens):
                continue
        matched.append(el)
    return matched[0] if len(matched)==1 else None


def match_dom_target(target,elements):
    query=normalize(target)
    query_core=_strip_stopwords(query)
    quoted=[normalize(s) for s in re.findall(r'["“«\']([^"”»\']+)["”»\']',target)]
    quoted_cores=[_strip_stopwords(q) for q in quoted if q]
    matches=[]
    for element in elements:
        aliases={normalize(a) for a in element.get('aliases',[element['label']]) if a}
        alias_cores={_strip_stopwords(a) for a in aliases if a}
        exact=query in aliases or (len(query_core)>=4 and query_core in alias_cores)
        # A quoted accessible label can omit a domain suffix or preposition, e.g. "Search in Amazon" vs "Search Amazon.com".
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
        if len(matches)==1:
            return matches[0]
        return _disambiguate_by_context_or_zone(query, [(el, normalize(el.get('label',''))) for el in matches])
    # Check if an element's label is contained in the query alongside disambiguating context or zone
    # e.g. "Click Details for Product 2" or "Sign in button in the header"
    partial_candidates=[]
    q_words=set(query.split())
    for element in elements:
        aliases=[normalize(a) for a in element.get('aliases',[element['label']]) if a]
        for a in aliases:
            a_words=a.split()
            if a and len(a)>=3 and all(w in q_words for w in a_words) and a in query:
                partial_candidates.append((element, a))
                break
    if partial_candidates:
        disambiguated=_disambiguate_by_context_or_zone(query, partial_candidates)
        if disambiguated is not None:
            return disambiguated
    # Generic search-bar requests may use a unique searchbox role; specific content queries (e.g. "search reviews") may not.
    is_search_bar_query=(
        query in SEARCH_BAR_TERMS
        or any(query.startswith(term+' ') for term in SEARCH_BAR_TERMS if term!='search')
    )
    if is_search_bar_query:
        matches=[e for e in elements if e.get('role')=='searchbox']
        return matches[0] if len(matches)==1 else None
    return None


def score_candidate_for_d1(target, element):
    """Score a DOM candidate for D1 visual disambiguation priority."""
    query=normalize(target)
    query_core=_strip_stopwords(query)
    q_tokens=set(query_core.split())
    quoted=[normalize(s) for s in re.findall(r'["“«\']([^"”»\']+)["”»\']',target)]
    aliases=[normalize(a) for a in element.get('aliases',[element.get('label','')]) if a]
    ctx=normalize(element.get('context',''))
    role=normalize(element.get('role',''))
    score=0.0
    for a in aliases:
        if not a:
            continue
        if a==query or a in quoted:
            score=max(score, 100.0)
        elif a in query or query in a:
            score=max(score, 70.0)
        a_tokens=set(_strip_stopwords(a).split())
        if q_tokens and a_tokens:
            overlap=len(q_tokens & a_tokens)
            if overlap:
                score=max(score, 30.0 * (overlap / max(1, len(q_tokens))) + 15.0 * (overlap / max(1, len(a_tokens))))
    if ctx and q_tokens:
        ctx_tokens=set(_strip_stopwords(ctx).split())
        ctx_overlap=len(q_tokens & ctx_tokens)
        if ctx_overlap:
            score += 20.0 * (ctx_overlap / max(1, len(q_tokens)))
    for r_name, r_terms in ROLE_SYNONYMS.items():
        if role==r_name and any(t in query for t in r_terms):
            score += 12.0
    requested_zones=_query_zones(query)
    if requested_zones and _element_matches_zone(element, requested_zones):
        score += 15.0
    return score


def select_d1_candidates(target, elements, max_single_stage=25):
    """
    Narrow or rank DOM candidates before D1 Set-of-Mark annotation.
    - If 2..max_single_stage elements strongly match the target label/tokens, return only those
      so D1 can choose in a single clean, cropped pass instead of scanning 60+ unrelated links.
    - Otherwise return all elements ordered by relevance so stage-1 groups prioritize top candidates.
    """
    if len(elements) <= 2:
        return list(elements)
    scored=[(score_candidate_for_d1(target, el), idx, el) for idx, el in enumerate(elements)]
    strong=[el for s, _, el in scored if s >= 45.0]
    if 2 <= len(strong) <= max_single_stage:
        return strong
    moderate=[el for s, _, el in scored if s >= 25.0]
    if 2 <= len(moderate) <= max_single_stage and len(elements) > max_single_stage:
        return moderate
    if any(s > 0 for s, _, _ in scored) and len(elements) > max_single_stage:
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [el for _, _, el in scored]
    return list(elements)


def format_d1_options(candidates):
    """
    Build choice descriptions for D1.
    Preserves exact `label` when labels are unique and have no extra disambiguating context,
    and appends `[zone / context]` when multiple candidates share the same label.
    """
    counts={}
    for el in candidates:
        lbl=el.get('label','')
        counts[lbl]=counts.get(lbl,0)+1
    options={}
    for el in candidates:
        lbl=el.get('label','')
        if counts.get(lbl,0) > 1:
            parts=[p for p in (el.get('role') or None, el.get('zone') or None, el.get('context') or None) if p]
            suffix=f" [{' | '.join(parts)}]" if parts else f" [#{el['id']}]"
            options[el['id']] = (lbl + suffix)[:180]
        else:
            options[el['id']] = lbl
    return options


def should_crop_candidates(image, elements, max_area_ratio=0.60):
    if not elements or len(elements) > 16:
        return False
    boxes=[e['box'] for e in elements]
    left=max(0,int(min(b[0] for b in boxes))-56)
    top=max(0,int(min(b[1] for b in boxes))-56)
    right=min(image.width,int(max(b[0]+b[2] for b in boxes))+56)
    bottom=min(image.height,int(max(b[1]+b[3] for b in boxes))+56)
    crop_area=max(1,(right-left)*(bottom-top))
    total_area=max(1,image.width*image.height)
    return (crop_area / total_area) <= max_area_ratio


def crop_candidates(image,elements,padding=48):
    if not elements:
        return image
    boxes=[e['box'] for e in elements]
    left=max(0,int(min(b[0] for b in boxes))-padding)
    top=max(0,int(min(b[1] for b in boxes))-padding)
    right=min(image.width,int(max(b[0]+b[2] for b in boxes))+padding)
    bottom=min(image.height,int(max(b[1]+b[3] for b in boxes))+padding)
    return image.crop((left,top,right,bottom))
