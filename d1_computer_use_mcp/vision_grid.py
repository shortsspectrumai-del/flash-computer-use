"""Coarse-to-fine 4x4 grid without coordinate generation."""
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont


@lru_cache(maxsize=16)
def _load_font(size):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def grid(image,enlarge=False):
    if image.width < 4 or image.height < 4:
        raise ValueError('Screenshot too small for a 4x4 grid')
    if enlarge and max(image.size)<384:
        scale=384/max(image.size)
        base=image if image.mode=='RGB' else image.convert('RGB')
        result=base.resize((round(image.width*scale),round(image.height*scale)),Image.Resampling.BILINEAR)
    else:
        result=image.copy() if image.mode=='RGB' else image.convert('RGB')
    draw = ImageDraw.Draw(result)
    font = _load_font(max(12,round(max(result.size)/768*16)))
    cells = {}
    for row in range(4):
        for col in range(4):
            label = f'{chr(65+row)}{col+1}'
            box = (col*image.width//4, row*image.height//4,
                   (col+1)*image.width//4, (row+1)*image.height//4)
            cells[label] = box
            l,t,r,b=(col*result.width//4,row*result.height//4,(col+1)*result.width//4,(row+1)*result.height//4)
            draw.rectangle((l,t,r-1,b-1), outline='red', width=1)
            cx, cy = (l+r)//2, (t+b)//2
            if (r-l)>=20 and (b-t)>=20:
                draw.line((cx-3,cy,cx+3,cy), fill='red', width=1)
                draw.line((cx,cy-3,cx,cy+3), fill='red', width=1)
            badge=draw.textbbox((0,0),label,font=font)
            draw.rectangle((l+1,t+1,l+badge[2]+5,t+badge[3]-badge[1]+5),fill='white')
            draw.text((l+2,t+2-badge[1]),label,fill='black',font=font)
    return result, cells


def refine(coarse, fine, origin=(0,0)):
    return (origin[0] + coarse[0] + (fine[0]+fine[2])//2,
            origin[1] + coarse[1] + (fine[1]+fine[3])//2)
