from PIL import Image
from d1_computer_use_mcp.vision_grid import grid, refine


def test_grid_covers_odd_sized_image():
    image = Image.new('RGB',(103,79),'white')
    annotated, cells = grid(image)
    assert image.getpixel((0,0)) == (255,255,255)
    assert annotated.size == image.size
    assert len(cells) == 16
    assert cells['D4'] == (77,59,103,79)
    assert sum((r-l)*(b-t) for l,t,r,b in cells.values()) == 103*79


def test_refine_coordinates_include_desktop_origin():
    assert refine((77,59,103,79), (19,15,26,20), (-100,50)) == (-1,126)
