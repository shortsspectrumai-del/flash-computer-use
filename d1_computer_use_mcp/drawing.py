"""Portable screen-coordinate paths, human trajectories, rich shapes, and canvas detection."""
import math

SHAPES = {'line','rectangle','ellipse','circle','triangle','diamond','star','arrow','heart','house','spiral','wave'}


def validate_path(points,canvas_bounds):
    if not isinstance(points,list) or not 2<=len(points)<=512:
        raise ValueError('Provide 2 to 512 path points')
    if canvas_bounds is None or len(canvas_bounds)!=4 or any(isinstance(v,bool) or not isinstance(v,int) for v in canvas_bounds):
        raise ValueError('canvas_bounds must be [x,y,width,height] in integer pixels')
    x,y,w,h=canvas_bounds
    if w<=0 or h<=0:
        raise ValueError('Canvas dimensions must be positive')
    for point in points:
        if not isinstance(point,(list,tuple)) or len(point)!=2 or any(isinstance(v,bool) or not isinstance(v,int) for v in point) or not x<=point[0]<x+w or not y<=point[1]<y+h:
            raise ValueError('Every path point must be inside the specified canvas')
    return points


def normalize_strokes(points_or_strokes, canvas_bounds):
    """Accept either a single polyline [[x,y],...] or multiple strokes [[[x,y],...],...] and validate all points."""
    if not isinstance(points_or_strokes, list) or not points_or_strokes:
        raise ValueError('Provide 2 to 512 path points')
    first = points_or_strokes[0]
    if isinstance(first, list) and first and isinstance(first[0], (list, tuple)):
        if len(points_or_strokes) > 64:
            raise ValueError('At most 64 strokes per drawing call')
        return [validate_path(stroke, canvas_bounds) for stroke in points_or_strokes]
    return [validate_path(points_or_strokes, canvas_bounds)]


def interpolate_stroke(points, step_px=8):
    """Subdivide segments into smooth intermediate drag points so Paint brushes never skip pixels,
    while always visiting every original vertex in exact order."""
    if len(points) < 2 or step_px <= 0:
        return [list(p) for p in points]
    result = [list(points[0])]
    for x1, y1 in points[1:]:
        x0, y0 = result[-1]
        dist = math.hypot(x1 - x0, y1 - y0)
        steps = max(1, min(64, int(dist // step_px)))
        for i in range(1, steps):
            t = i / steps
            px = round(x0 + (x1 - x0) * t)
            py = round(y0 + (y1 - y0) * t)
            pt = [int(px), int(py)]
            if pt != result[-1] and pt != [x1, y1]:
                result.append(pt)
        if result[-1] != [x1, y1]:
            result.append([int(x1), int(y1)])
    return result


def shape_points(shape,x,y,width,height):
    if shape not in SHAPES or width<1 or height<1:
        raise ValueError(f'Use one of {sorted(SHAPES)} with positive dimensions')
    if shape=='line':
        return [[x,y],[x+width,y+height]]
    if shape=='rectangle':
        return [[x,y],[x+width,y],[x+width,y+height],[x,y+height],[x,y]]
    if shape in {'ellipse','circle'}:
        rx = min(width, height)/2 if shape=='circle' else width/2
        ry = rx if shape=='circle' else height/2
        cx, cy = x + width/2, y + height/2
        points=[[round(cx+rx*math.cos(i*2*math.pi/64)),round(cy+ry*math.sin(i*2*math.pi/64))] for i in range(64)]
        return points+[points[0]]
    if shape=='triangle':
        return [[round(x+width/2),y],[x+width,y+height],[x,y+height],[round(x+width/2),y]]
    if shape=='diamond':
        cx, cy = round(x+width/2), round(y+height/2)
        return [[cx,y],[x+width,cy],[cx,y+height],[x,cy],[cx,y]]
    if shape=='star':
        cx, cy = x + width/2, y + height/2
        rx, ry = width/2, height/2
        pts=[]
        for i in range(10):
            angle = -math.pi/2 + i*math.pi/5
            scale = 1.0 if i%2==0 else 0.4
            pts.append([round(cx + rx*scale*math.cos(angle)), round(cy + ry*scale*math.sin(angle))])
        return pts+[pts[0]]
    if shape=='arrow':
        cy = round(y + height/2)
        head_x = x + round(width*0.65)
        return [[x,cy],[x+width,cy],[head_x,y],[x+width,cy],[head_x,y+height]]
    if shape=='heart':
        pts=[]
        for i in range(64):
            t = i * 2 * math.pi / 64
            hx = 16 * (math.sin(t) ** 3)
            hy = -(13 * math.cos(t) - 5 * math.cos(2*t) - 2 * math.cos(3*t) - math.cos(4*t))
            # Normalize hx in [-16, 16] and hy in [-17, 15] into [x, x+width] x [y, y+height]
            px = round(x + (hx + 16) / 32 * width)
            py = round(y + (hy + 17) / 32 * height)
            pts.append([max(x, min(x+width, px)), max(y, min(y+height, py))])
        return pts+[pts[0]]
    if shape=='house':
        roof_y = y + round(height * 0.4)
        cx = round(x + width / 2)
        return [[x,roof_y],[cx,y],[x+width,roof_y],[x,roof_y],[x,y+height],[x+width,y+height],[x+width,roof_y]]
    if shape=='wave':
        pts=[]
        for i in range(49):
            t = i / 48
            px = round(x + t * width)
            py = round(y + height/2 + (height/2)*math.sin(t * 4 * math.pi))
            pts.append([px, max(y, min(y+height, py))])
        return pts
    # spiral
    cx, cy = x + width/2, y + height/2
    rx, ry = width/2, height/2
    pts=[]
    for i in range(65):
        t = i / 64
        angle = t * 6 * math.pi
        pts.append([round(cx + rx*t*math.cos(angle)), round(cy + ry*t*math.sin(angle))])
    return pts


def detect_canvas_from_image(image, origin=(0, 0)):
    """Locate the primary drawing sheet/canvas inside a desktop screenshot (e.g. Paint, KolourPaint, Pinta).
    Scans for the largest bright/uniform interior work area excluding top toolbars and window borders."""
    w, h = image.size
    if w < 64 or h < 64:
        return [origin[0], origin[1], w, h]
    rgb = image if image.mode == 'RGB' else image.convert('RGB')
    small_w, small_h = min(160, w), min(120, h)
    thumb = rgb.resize((small_w, small_h))
    px = thumb.load()
    is_sheet = [[False]*small_w for _ in range(small_h)]
    for r in range(small_h):
        for c in range(small_w):
            rv, gv, bv = px[c, r]
            # Drawing sheets in Paint/KolourPaint/Pinta are typically bright white/light neutral areas
            if rv >= 230 and gv >= 230 and bv >= 230 and max(rv, gv, bv) - min(rv, gv, bv) <= 18:
                is_sheet[r][c] = True
    # Find largest rectangle of True in histogram
    heights = [0]*small_w
    best_area = 0
    best_rect = None
    for r in range(small_h):
        for c in range(small_w):
            heights[c] = heights[c] + 1 if is_sheet[r][c] else 0
        stack = []
        for c in range(small_w + 1):
            cur_h = heights[c] if c < small_w else 0
            start_c = c
            while stack and stack[-1][1] > cur_h:
                sc, sh = stack.pop()
                area = (c - sc) * sh
                if area > best_area:
                    best_area = area
                    best_rect = (sc, r - sh + 1, c - sc, sh)
                start_c = sc
            stack.append((start_c, cur_h))
    if best_rect and best_area >= (small_w * small_h * 0.08):
        sx = w / small_w
        sy = h / small_h
        cx = int(round(best_rect[0] * sx)) + 4
        cy = int(round(best_rect[1] * sy)) + 4
        cw = max(16, int(round(best_rect[2] * sx)) - 8)
        ch = max(16, int(round(best_rect[3] * sy)) - 8)
        return [origin[0] + cx, origin[1] + cy, cw, ch]
    # Safe central fallback inside the active monitor/window (skipping top toolbar/menubar and bottom taskbar)
    cx = int(round(w * 0.12))
    cy = int(round(h * 0.18))
    cw = max(32, int(round(w * 0.76)))
    ch = max(32, int(round(h * 0.68)))
    return [origin[0] + cx, origin[1] + cy, cw, ch]


def human_path(start, end, bounds=None, steps=None):
    """Generate a fast, human-like minimum-jerk trajectory with a subtle natural wrist arc.
    Always lands on the exact integer endpoint end=(x1, y1)."""
    x0, y0 = int(round(start[0])), int(round(start[1]))
    x1, y1 = int(round(end[0])), int(round(end[1]))
    dx, dy = x1 - x0, y1 - y0
    dist = math.hypot(dx, dy)
    if dist < 4:
        return [[x1, y1]]
    if steps is None:
        steps = max(4, min(10, int(dist // 45) + 4))
    if steps <= 1:
        return [[x1, y1]]
    # Subtle perpendicular wrist arc (~5% of distance, capped at 16px), alternating sign deterministically
    sign = 1 if ((x0 + y0 + x1 + y1) & 1) == 0 else -1
    arc = min(16.0, dist * 0.05) * sign
    nx, ny = -dy / dist, dx / dist
    pts = []
    for i in range(1, steps + 1):
        t = i / steps
        # Minimum-jerk velocity profile: s(t) = 10*t^3 - 15*t^4 + 6*t^5
        s = t * t * t * (10.0 + t * (-15.0 + 6.0 * t))
        # Smooth bell-shaped lateral offset that vanishes at t=0 and t=1
        bell = 4.0 * s * (1.0 - s)
        px = round(x0 + dx * s + nx * arc * bell)
        py = round(y0 + dy * s + ny * arc * bell)
        if bounds is not None:
            bx, by, bw, bh = bounds
            px = max(bx, min(bx + bw - 1, px))
            py = max(by, min(by + bh - 1, py))
        pt = [int(px), int(py)]
        if not pts or pts[-1] != pt:
            pts.append(pt)
    if not pts or pts[-1] != [x1, y1]:
        pts.append([x1, y1])
    return pts
