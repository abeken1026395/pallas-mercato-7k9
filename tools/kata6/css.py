#!/usr/bin/env python3
"""写し取った結果（capture.py の出力 cap_<名前>.json）から、ページごとの型 assets/kata/<名前>.css を作る。
使い方：python3 tools/kata6/css.py <cap の置き場> <docs の根>"""
import json, os, re, sys
NUMD='font-family:"Barlow Condensed","Hiragino Sans",-apple-system,sans-serif !important;font-variant-numeric:tabular-nums !important;letter-spacing:.01em !important'
TITD='font-family:"Dela Gothic One",-apple-system,"Hiragino Sans",sans-serif !important;font-weight:400 !important;color:#f2f2f0 !important;-webkit-text-fill-color:#f2f2f0 !important;letter-spacing:.02em !important;background:none !important;padding-bottom:10px !important;border-bottom:1px solid rgba(212,176,106,.6) !important;margin-bottom:12px !important'
def css_for(cap):
    out=["/* 第6版：第5版の型が塗った結果を、作るときに写し取ったもの（tools/kata6/css.py が生成。手で直さない） */"]
    for sel,o in sorted(cap["rules"].items()):
        if not re.search(r"[.#\[]", sel):
            # class・id・属性を持たない形だけの規則（div:nth-of-type(2)>… のような）で、金の地（選ばれた見た目）か隠す規則は、地の色・隠す・文字の色を外す。
            # 写し取ったときに無かった部品（選手を開いた中身など）にも当たり、関係のない部品が金の地になったり消えたりしたため
            bg = o.get("background-color", "")
            m = re.match(r"rgb\((\d+), (\d+), (\d+)\)$", bg)
            loud = bool(m) and max(map(int, m.groups())) - min(map(int, m.groups())) > 80   # 金・黄など、色の強い地（選ばれた見た目）
            if o.get("display") == "none" or loud:
                o = {k: v for k, v in o.items() if k not in ("background-color", "background-image", "display", "color", "-webkit-text-fill-color")}
        sl=":root "+sel.replace("[data-ko=","[style=")
        decl=[]
        for k,v in sorted(o.items()):
            if k=="@kataNum": out.append(sl+"{"+NUMD+"}")
            elif k=="@kataTitle": out.append(sl+"{"+TITD+"}")
            elif k=="@kataNoBefore": out.append(sl+"::before{display:none !important}")
            elif k=="@kataNoAfter": out.append(sl+"::after{display:none !important}")
            elif k=="@kskip": decl.append("border-radius:0 !important")
            else: decl.append("%s:%s !important"%(k,v))
        if decl: out.append(sl+"{"+";".join(decl)+"}")
    return "\n".join(out)+"\n"

def main():
    src, root = sys.argv[1], sys.argv[2]
    out = os.path.join(root, "assets", "kata"); os.makedirs(out, exist_ok=True)
    for f in sorted(os.listdir(src)):
        if not (f.startswith("cap_") and f.endswith(".json")): continue
        name = f[4:-5]
        css = css_for(json.load(open(os.path.join(src, f))))
        open(os.path.join(out, name + ".css"), "w", encoding="utf-8", newline="\n").write(css)
        print(name, len(css))

if __name__ == "__main__":
    main()
