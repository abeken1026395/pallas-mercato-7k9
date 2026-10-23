# 写しの段階で、ページ自身の CSS と script の中の紫を金に置き換える（状態で切り替わる色も、ページ自身の色として金になる）。
# 実行時に上から塗る方式だと、タブなどの状態の切り替えと追いかけ合って色がブレるため（けん 10-23）
import re, colorsys
GOLD_BG = "#c8a45e"; GOLD_TX = "#dcbd78"; DARK = "#10141a"
def hexrgb(h):
    h = h.lstrip("#")
    if len(h) == 3: h = "".join(c*2 for c in h)
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
def is_purple(rgb):
    r, g, b = [x/255 for x in rgb]
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    mx, mn = max(r, g, b), min(r, g, b)
    sat = (mx - mn) / mx if mx else 0
    return 240 <= h*360 <= 345 and sat >= 0.3 and l >= 0.3  # 型（kata2 以降）と同じく、ピンクまで含める
def gold_for(rgb):
    l = colorsys.rgb_to_hls(*[x/255 for x in rgb])[1]
    return GOLD_TX if l >= 0.66 else GOLD_BG
HEX = re.compile(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})(?![0-9a-fA-F])")
RGB = re.compile(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+)\s*)?\)")
def sub_colors(text):
    def h(m):
        rgb = hexrgb(m.group(0))
        return gold_for(rgb) if is_purple(rgb) else m.group(0)
    def r(m):
        rgb = tuple(int(m.group(i)) for i in (1, 2, 3))
        if not is_purple(rgb): return m.group(0)
        g = hexrgb(gold_for(rgb))
        return "rgba(%d,%d,%d,%s)" % (g + (m.group(4),)) if m.group(4) else "rgb(%d,%d,%d)" % g
    return RGB.sub(r, HEX.sub(h, text))
RULE = re.compile(r"([^{}]+)\{([^{}]*)\}")
def fix_css(css):
    def rule(m):
        sel, decl = m.group(1), m.group(2)
        had = any(is_purple(hexrgb(x)) for x in HEX.findall(decl) if re.search(r"background", decl))
        nd = sub_colors(decl)
        if had and re.search(r"background(-color)?\s*:\s*#c8a45e", nd):
            nd = re.sub(r"(?<![-\w])color\s*:\s*(#fff(?:fff)?|white)\b", "color:" + DARK, nd)
        return sel + "{" + nd + "}"
    return RULE.sub(rule, css)
YVAR = re.compile(r"(--(?:acc|accent|gold|yellow|mido|hl|key|ki)\b[\w-]*\s*:\s*)(#[0-9a-fA-F]{3,6})")
def is_yellow(rgb):
    r, g, b = [x/255 for x in rgb]
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    mx, mn = max(r, g, b), min(r, g, b)
    return 38 <= h*360 <= 58 and ((mx - mn) / mx if mx else 0) >= 0.55 and l >= 0.45
def gold_vars(css):
    # 差し色の変数（--acc・--accent など）が黄なら金に。枠番の変数（--w5 など）は名前が違うので変わらない
    return YVAR.sub(lambda m: m.group(1) + (GOLD_TX if is_yellow(hexrgb(m.group(2))) else m.group(2)), css)
def transform(html):
    html = re.sub(r"(<style[^>]*>)(.*?)(</style>)", lambda m: m.group(1) + gold_vars(fix_css(m.group(2))) + m.group(3), html, flags=re.S)
    html = re.sub(r"(<script(?![^>]*\bsrc=)[^>]*>)(.*?)(</script>)", lambda m: m.group(1) + sub_colors(m.group(2)) + m.group(3), html, flags=re.S)
    return html
