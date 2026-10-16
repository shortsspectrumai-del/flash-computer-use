from functools import lru_cache
from PIL import ImageDraw, ImageFont


@lru_cache(maxsize=16)
def _load_font(size):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _overlaps(a, b):
    return not (a[2] <= b[0] or a[0] >= b[2] or a[3] <= b[1] or a[1] >= b[3])


def annotate(image, elements):
    result = image.copy() if image.mode == 'RGB' else image.convert('RGB')
    draw = ImageDraw.Draw(result)
    font = _load_font(max(14, round(max(image.size)/768*16)))
    placed = []
    element_boxes = [(int(e['box'][0]), int(e['box'][1]), int(e['box'][0]+e['box'][2]), int(e['box'][1]+e['box'][3])) for e in elements]
    for idx, element in enumerate(elements):
        x, y, w, h = element['box']
        x, y, w, h = int(round(x)), int(round(y)), int(round(w)), int(round(h))
        label = str(element['id'])
        # High-contrast double outline so boxes stand out on both dark and light web themes
        draw.rectangle((max(0, x-1), max(0, y-1), min(result.width-1, x+w+1), min(result.height-1, y+h+1)), outline='white', width=1)
        draw.rectangle((x, y, x+w, y+h), outline='#e60000', width=2)
        badge = draw.textbbox((0, 0), label, font=font)
        bw = badge[2] - badge[0] + 8
        bh = badge[3] - badge[1] + 6
        # Prefer exterior positions around the element so the badge never covers small buttons/icons
        candidates_pos = [
            (max(0, min(result.width-bw, x)), max(0, y-bh-1)),
            (max(0, min(result.width-bw, x+w-bw)), max(0, y-bh-1)),
            (max(0, min(result.width-bw, x)), min(result.height-bh, y+h+1)),
            (max(0, min(result.width-bw, x+w-bw)), min(result.height-bh, y+h+1)),
            (max(0, x-bw-1), max(0, min(result.height-bh, y))),
            (min(result.width-bw, x+w+1), max(0, min(result.height-bh, y))),
            (max(0, min(result.width-bw, x + (w-bw)//2)), max(0, y-bh-1)),
            (max(0, min(result.width-bw, x)), max(0, min(result.height-bh, y))),
        ]
        bx, by = candidates_pos[0]
        found = False
        for cx, cy in candidates_pos:
            rect = (cx, cy, cx+bw, cy+bh)
            if not any(_overlaps(rect, p) for p in placed) and not any(
                i != idx and _overlaps(rect, eb) for i, eb in enumerate(element_boxes)
            ):
                bx, by = cx, cy
                found = True
                break
        if not found:
            for cx, cy in candidates_pos:
                rect = (cx, cy, cx+bw, cy+bh)
                if not any(_overlaps(rect, p) for p in placed):
                    bx, by = cx, cy
                    break
        rect = (bx, by, bx+bw, by+bh)
        placed.append(rect)
        draw.rectangle(rect, fill='#ffeb3b', outline='black', width=1)
        draw.text((bx+4, by+2-badge[1]), label, fill='black', font=font)
    return result
