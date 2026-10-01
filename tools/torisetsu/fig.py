from PIL import Image, ImageDraw, ImageFont

FONT_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
ORANGE = (255, 122, 0)
WHITE = (255, 255, 255)


def callout(src, dst, rows, trim=None, pad=130, r=40, line_to=52,
            color=ORANGE):
    im = Image.open(src).convert("RGB")
    if trim:
        im = im.crop(trim)
    w, h = im.size
    canvas = Image.new("RGB", (w + pad, h), WHITE)
    canvas.paste(im, (pad, 0))
    d = ImageDraw.Draw(canvas)
    f = ImageFont.truetype(FONT_B, int(r * 1.15))
    end = pad + line_to
    for i, y in enumerate(rows, 1):
        cx = r + 12
        d.line([cx + r, y, end, y], fill=color, width=8)
        d.ellipse([cx - r, y - r, cx + r, y + r], fill=color, outline=WHITE,
                  width=5)
        t = str(i)
        bb = d.textbbox((0, 0), t, font=f)
        d.text((cx - (bb[2] - bb[0]) / 2 - bb[0],
                y - (bb[3] - bb[1]) / 2 - bb[1]), t, font=f, fill=WHITE)
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
