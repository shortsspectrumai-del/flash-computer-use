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
    for element in elements:
        x,y,w,h = element['box']
        label = str(element['id'])
        draw.rectangle((x,y,x+w,y+h), outline='red', width=2)
        badge = draw.textbbox((0,0),label,font=font)
        bw = badge[2]-badge[0]+8
        bh = badge[3]-badge[1]+6
        candidates_pos = [
            (max(0, min(result.width-bw, x)), max(0, y-bh)),
            (max(0, min(result.width-bw, x+w-bw)), max(0, y-bh)),
            (max(0, min(result.width-bw, x)), min(result.height-bh, y+h)),
            (max(0, min(result.width-bw, x)), max(0, min(result.height-bh, y))),
        ]
        bx, by = candidates_pos[0]
        for cx, cy in candidates_pos:
            rect = (cx, cy, cx+bw, cy+bh)
            if not any(_overlaps(rect, p) for p in placed):
                bx, by = cx, cy
                break
        rect = (bx, by, bx+bw, by+bh)
        placed.append(rect)
        draw.rectangle(rect, fill='yellow', outline='black', width=1)
        draw.text((bx+4, by+2-badge[1]), label, fill='black', font=font)
    return result
