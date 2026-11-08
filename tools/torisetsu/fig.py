from PIL import Image, ImageDraw, ImageFont

FONT_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
ORANGE = (255, 122, 0)
WHITE = (255, 255, 255)


def clear_x(im, y, half=7, tol=34):
    """y の前後 half 行で、左端の地の色と違う画素が最初に出てくる x。"""
    w, h = im.size
    px = im.load()
    y = int(round(y))
    best = w
    for yy in range(max(0, y - half), min(h, y + half + 1)):
        bg = px[0, yy]
        for x in range(1, best):
            c = px[x, yy]
            if abs(c[0] - bg[0]) + abs(c[1] - bg[1]) + abs(c[2] - bg[2]) > tol:
                best = x
                break
    return best


def ink_x(im, y, tol=34, half=4):
    """clear_x と同じだが、カードの縦の枠線（細い縦線）は越えて、その先の最初の文字までの x を返す。"""
    w, h = im.size
    px = im.load()
    y = int(round(y))
    best = w
    for yy in range(max(0, y - half), min(h, y + half + 1)):
        bg = px[0, yy]
        x = 1
        while x < best:
            c = px[x, yy]
            if abs(c[0] - bg[0]) + abs(c[1] - bg[1]) + abs(c[2] - bg[2]) > tol:
                run = 1
                while x + run < w and run <= 10:
                    c2 = px[x + run, yy]
                    if abs(c2[0] - c[0]) + abs(c2[1] - c[1]) + abs(c2[2] - c[2]) > tol:
                        break
                    run += 1
                vert = all(0 <= yy + dy < h and sum(abs(px[x, yy + dy][k] - c[k]) for k in range(3)) <= tol
                           for dy in (-24, -12, 12, 24))
                if run <= 10 and vert:            # 縦の枠線：越えて、その内側の色を新しい地にする
                    x += run
                    bg = px[min(w - 1, x + 2), yy]
                    continue
                best = x
                break
            x += 1
    return best


def col_clear(im, x, y0, y1, tol=34):
    """x の列（前後3画素）が、y0〜y1 のあいだ地の色のままか（縦の線を引いても何も横切らないか）。"""
    px = im.load()
    a, b = sorted((int(y0), int(y1)))
    for yy in range(a, b + 1):
        bg = px[max(0, x - 10), yy]
        for xx in (x - 3, x, x + 3):
            c = px[xx, yy]
            if abs(c[0] - bg[0]) + abs(c[1] - bg[1]) + abs(c[2] - bg[2]) > tol:
                return False
    return True


def route(im, y, t, taken, r, reach=260):
    """その高さでは手前に別の文字があって線が届かないとき、近くの空いた行を探す。
    返り値 (yy, xv)：丸を yy に置き、横線を xv まで引き、そこから縦に y まで下ろして t の手前へ短く入る。"""
    h = im.size[1]
    xv = t - 16
    for d in range(12, reach, 2):
        for yy in (y - d, y + d):
            if yy < r + 4 or yy > h - r - 4:
                continue
            if any(abs(yy - o) < 2 * r + 8 for o in taken):
                continue
            if clear_x(im, yy, half=26) < xv + 6:
                continue
            if col_clear(im, xv, yy, y):
                return yy, xv
    return None


def callout(src, dst, rows, trim=None, pad=130, r=40, line_to=52,
            color=ORANGE, ends=None, elbow=()):
    im = Image.open(src).convert("RGB")
    if trim:
        im = im.crop(trim)
    w, h = im.size
    canvas = Image.new("RGB", (w + pad, h), WHITE)
    canvas.paste(im, (pad, 0))
    d = ImageDraw.Draw(canvas)
    f1 = ImageFont.truetype(FONT_B, int(r * 1.15))
    f2 = ImageFont.truetype(FONT_B, int(r * 0.92))     # 2けたは小さくして丸に収める
    cx = r + 12
    plan = []
    for i, y in enumerate(rows, 1):
        t = None if ends is None else ends[i - 1] + 24          # 指したい要素の左端
        cx0 = clear_x(im, y)
        if t is not None and i in elbow and ink_x(im, y) < t - 40:                       # 手前に別の文字がある＝その高さでは届かない
            others = [o for j, o in enumerate(rows) if j != i - 1] + [p[0] for p in plan]
            got = route(im, y, t, others, r)
            if got:
                plan.append((got[0], "elbow", y, got[1]))
                print("  折れ線：", dst.rsplit("/", 1)[-1], i)
                continue
            print("  経路なし：", dst.rsplit("/", 1)[-1], i)
        e = line_to if t is None else max(0, t - 24)
        e = min(e, cx0 - 18)
        plan.append((y, "flat", y, e))
    for i, (yb, kind, y, x) in enumerate(plan, 1):
        if kind == "flat":
            if pad + x > cx + r:
                d.line([cx + r, yb, pad + x, yb], fill=color, width=8)
        else:
            xv = pad + x
            d.line([cx + r, yb, xv, yb], fill=color, width=8)
            d.line([xv, yb, xv, y], fill=color, width=8)
            d.line([xv - 4, y, xv + 10, y], fill=color, width=8)
        d.ellipse([cx - r, yb - r, cx + r, yb + r], fill=color, outline=WHITE, width=5)
        t = str(i)
        f = f1 if len(t) == 1 else f2
        bb = d.textbbox((0, 0), t, font=f)
        d.text((cx - (bb[2] - bb[0]) / 2 - bb[0],
                yb - (bb[3] - bb[1]) / 2 - bb[1]), t, font=f, fill=(18, 26, 40))
    canvas.save(dst)
    return canvas.size


def ruler(src, dst, trim=None, step=100):
    f = ImageFont.truetype(FONT_B, 26)
    im = Image.open(src).convert("RGB")
    if trim:
        im = im.crop(trim)
    w, h = im.size
    pad = 120
    c = Image.new("RGB", (w + pad, h), WHITE)
    c.paste(im, (pad, 0))
    d = ImageDraw.Draw(c)
    for y in range(0, h, step):
        d.line([pad - 34, y, pad + 44, y], fill=(230, 40, 40), width=4)
        d.text((4, max(0, y - 14)), str(y), font=f, fill=(200, 20, 20))
    c.save(dst)
    return c.size
