#!/usr/bin/env python3
"""サイト共通の型 第6版を本番のページに入れる（2026-10-24 けん「切り替えが済んだので、第6版を本番に反映して」）。

第6版の作り：
  1. ページ自身の CSS・script の紫とピンクを金に置き換える（statPurple.py）
  2. 共通の型 assets/kata/kata.css と、動き assets/ugoki.css・assets/ugoki.js を読む
  3. ページごとの型 assets/kata/<名前>.css を読む。中身は、第5版の型（実行時に1つずつ塗る方式）が塗った結果を、
     作るときにブラウザで写し取ったもの（capture.py・analyze.js）。表示のときに色や形を計算しない
  4. 軽い処理だけの assets/kata/kata.js（絵文字・飾りの矢印の除去、題字の印、数字だけの部品の印 kataN）

使い方（リポジトリの一番上で）：
  python3 tools/kata6/build.py apply <docs の根> cap    写し取り用（kata.js の代わりに第5版の型 cap.js を読む）
  python3 tools/kata6/build.py apply <docs の根> final  本番用（写し取った CSS と kata.js を読む）
  python3 tools/kata6/build.py templates                出走表・モーターのテンプレート（scripts/）に入れる
何度かけても同じ結果になる（前に入れた分を外してから入れ直す）。
"""
import os, re, sys, hashlib
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import statPurple

# (docs からのパス, 名前, 型をかけるか)
PAGES = [
    ("index.html", "top"), ("highlights/index.html", "highlights"), ("racers/index.html", "racers"),
    ("results/index.html", "results"), ("motor/index.html", "motor"), ("motor-maintenance/index.html", "motorMaintenance"),
    ("players/index.html", "players"), ("players/card.html", "playersCard"), ("payouts/index.html", "payouts"),
    ("stadium/index.html", "stadium"), ("kensho/index.html", "kensho"), ("kensho/flow/index.html", "kenshoFlow"),
    ("kensho/fmochi/index.html", "kenshoFmochi"), ("kensho/jimoto/index.html", "kenshoJimoto"),
    ("kensho/kado/index.html", "kenshoKado"), ("kensho/kisetsu/index.html", "kenshoKisetsu"),
    ("kensho/ninki/index.html", "kenshoNinki"), ("kensho/shobugake/index.html", "kenshoShobugake"),
    ("kensho/taiju/index.html", "kenshoTaiju"), ("kensho/tilt/index.html", "kenshoTilt"),
    ("glossary/index.html", "glossary"), ("fan/index.html", "fan"), ("announcers/index.html", "announcers"),
    ("updates/index.html", "updates"), ("torisetsu/index.html", "torisetsu"), ("uranai/index.html", "uranai"),
    # 2026-10-24 追加（けん「第6版の対象に入っていなかったページも進めていこう」）：万舟の24場の各ページ・検証10・占いの住之江版2つ
    ("amagasaki-payouts/index.html", "payoutsAmagasaki"),
    ("ashiya-payouts/index.html", "payoutsAshiya"),
    ("biwako-payouts/index.html", "payoutsBiwako"),
    ("edogawa-payouts/index.html", "payoutsEdogawa"),
    ("fukuoka-payouts/index.html", "payoutsFukuoka"),
    ("gamagori-payouts/index.html", "payoutsGamagori"),
    ("hamanako-payouts/index.html", "payoutsHamanako"),
    ("heiwajima-payouts/index.html", "payoutsHeiwajima"),
    ("karatsu-payouts/index.html", "payoutsKaratsu"),
    ("kiryu-payouts/index.html", "payoutsKiryu"),
    ("kojima-payouts/index.html", "payoutsKojima"),
    ("marugame-payouts/index.html", "payoutsMarugame"),
    ("mikuni-payouts/index.html", "payoutsMikuni"),
    ("miyajima-payouts/index.html", "payoutsMiyajima"),
    ("naruto-payouts/index.html", "payoutsNaruto"),
    ("omura-payouts/index.html", "payoutsOmura"),
    ("shimonoseki-payouts/index.html", "payoutsShimonoseki"),
    ("suminoe-payouts/index.html", "payoutsSuminoe"),
    ("tamagawa-payouts/index.html", "payoutsTamagawa"),
    ("toda-payouts/index.html", "payoutsToda"),
    ("tokoname-payouts/index.html", "payoutsTokoname"),
    ("tokuyama-payouts/index.html", "payoutsTokuyama"),
    ("tsu-payouts/index.html", "payoutsTsu"),
    ("wakamatsu-payouts/index.html", "payoutsWakamatsu"),
    ("kensho/tenji/index.html", "kenshoTenji"),
    ("aisho-suminoe/index.html", "aishoSuminoe"), ("shobuun-suminoe/index.html", "shobuunSuminoe"),
]
# 占いは型をかけない（けん 10-23「占いページの見た目は元のページの方が良かった。戻せ」）。動きだけ
LINK_ONLY = {"uranai", "aishoSuminoe", "shobuunSuminoe"}  # 占いの住之江版も占いと同じ扱い
# トップと選手図鑑は、試作の段階で手で直した色を使う（紫→金の置き換えはしない）
NO_PURPLE = {"top", "players", "uranai", "aishoSuminoe", "shobuunSuminoe"}
GENERATED = {"racers": "scripts/template_racers.html", "motor": "scripts/template.html"}

B0, B1 = "<!-- kata6:head -->", "<!-- /kata6:head -->"
E0, E1 = "<!-- kata6:body -->", "<!-- /kata6:body -->"

RACERS_CSS = """<style>
.rbtn{background:#12233a !important;border:1px solid #3d5a80 !important;border-radius:0 !important}
.rbtn .rno{color:#eef2f5 !important}
.rbtn .dl{color:#c8d3dd !important}
.rbtn.closed{background:transparent !important;border:1px dashed #2b4568 !important}
.rbtn.closed .rno{color:#6f8296 !important}
.rbtn.closed .dl,.rbtn.closed .rdone{color:#6f8296 !important}
.rbtn:not(.closed):first-child,.rbtn.closed + .rbtn:not(.closed){background:#c8a45e !important;border-color:#c8a45e !important}
.rbtn:not(.closed):first-child .rno,.rbtn.closed + .rbtn:not(.closed) .rno,.rbtn:not(.closed):first-child .dl,.rbtn.closed + .rbtn:not(.closed) .dl{color:#10141a !important;font-weight:800 !important}
.rbtn.chushi,.rbtn.chushi.closed{background:transparent !important;border:1px solid #93a5b6 !important}
.rbtn.chushi .rno,.rbtn.chushi .dl{color:#c8d3dd !important}
.cd{border-radius:0 !important}
.cd-open{background:transparent !important;color:#eef2f5 !important;border:1px solid #3d5a80 !important}
.cd-soon{background:#c8a45e !important;color:#10141a !important;border:1px solid #c8a45e !important}
.cd-closed{background:transparent !important;color:#6f8296 !important;border:1px dashed #2b4568 !important}
</style>
"""
TOP_CSS = ('<style>html{background:linear-gradient(180deg,#1b3a5e 0,#132b46 360px,#0d1c2f 900px,#0a1422 1500px) #0a1422 !important;'
           'background-repeat:no-repeat !important}</style>\n<script>window.KATA_GRAD=1</script>\n')
SQUARE = "<style>*,*::before,*::after{border-radius:0 !important}</style>\n"
NICK = """<script>
/* 二つ名・異名は了承済みの形（札にせず小さな文字）に保つ */
(function(){
  var SEL = 'span[style*="padding: 1px 7px"][style*="white-space: nowrap"], span[data-kata-skip]';
  function plain(){ document.querySelectorAll(SEL).forEach(function(e){ e.setAttribute("data-kata-skip", "");
    [["background","transparent"],["background-color","transparent"],["border","0"],["box-shadow","none"],["padding","0"],["font-size","11px"],["letter-spacing","0"],["margin-right","10px"],["color","#c9d3dd"],["-webkit-text-fill-color","#c9d3dd"]].forEach(function(kv){ e.style.setProperty(kv[0], kv[1], "important"); }); }); }
  var t = null;
  function soon(){ clearTimeout(t); t = setTimeout(plain, 120); }
  function start(){ plain(); new MutationObserver(function(){ plain(); soon(); }).observe(document.body, { childList: true, subtree: true }); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();
</script>
"""
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600;700&amp;family=Dela+Gothic+One&amp;display=swap" rel="stylesheet">\n')


def ver(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()[:8] if os.path.exists(path) else "0"


def strip(t):
    t = re.sub(re.escape(B0) + r".*?" + re.escape(B1) + r"\n?", "", t, flags=re.S)
    return re.sub(re.escape(E0) + r".*?" + re.escape(E1) + r"\n?", "", t, flags=re.S)


def ins_before_last(t, pat, new):
    ms = list(re.finditer(pat, t, flags=re.I)); assert ms, pat
    m = ms[-1]; return t[:m.start()] + new + t[m.start():]


def apply(t, name, rel, root, mode):
    """rel：docs からのパス。root：docs の根（?v= の計算に使う）。"""
    t = strip(t)
    if name not in NO_PURPLE:
        t = statPurple.transform(t)
    up = "../" * rel.count("/")
    A = up + "assets/"
    v = lambda p: ver(os.path.join(root, "assets", p))
    head = B0 + "\n"
    if name not in LINK_ONLY:
        head += FONTS + '<link rel="stylesheet" href="%skata/kata.css?v=%s">\n' % (A, v("kata/kata.css"))
        if mode == "final":
            head += '<link rel="stylesheet" href="%skata/%s.css?v=%s">\n' % (A, name, v("kata/%s.css" % name))
    head += '<link rel="stylesheet" href="%sugoki.css?v=%s">\n' % (A, v("ugoki.css"))
    if name == "racers": head += RACERS_CSS
    if name == "top": head += TOP_CSS
    if name in ("top", "players"): head += SQUARE
    if name == "players": head += '<link rel="stylesheet" href="%skata/players.css?v=%s">\n' % (A, v("kata/players.css"))
    head += B1 + "\n"
    t = ins_before_last(t, r"</head>", head)
    body = E0 + "\n"
    if name == "players": body += '<script src="%skata/players.js?v=%s"></script>\n' % (A, v("kata/players.js")) + NICK
    if name not in LINK_ONLY:
        js = "kata/cap.js" if mode == "cap" else "kata/kata.js"
        body += '<script src="%s%s?v=%s"></script>\n' % (A, js, v(js))
    body += '<script src="%sugoki.js?v=%s"></script>\n' % (A, v("ugoki.js"))
    body += E1 + "\n"
    return ins_before_last(t, r"</body>", body)


def main():
    cmd = sys.argv[1]
    if cmd == "apply":
        root, mode = sys.argv[2], sys.argv[3]
        gen = "--gen" in sys.argv   # 写し（手元の確認用）では、生成物にもかける
        only = set(a for a in sys.argv[4:] if not a.startswith("--"))
        for rel, name in PAGES:
            if only and name not in only: continue
            p = os.path.join(root, rel)
            if not os.path.exists(p): print("無い", p); continue
            if mode == "final" and name in GENERATED and not gen: continue  # 生成物は直接書かない（テンプレートから作り直す）
            t = open(p, encoding="utf-8").read()
            open(p, "w", encoding="utf-8", newline="\n").write(apply(t, name, rel, root, mode))
            print(mode, rel)
    elif cmd == "templates":
        for name, tp in GENERATED.items():
            rel = dict((n, r) for r, n in PAGES)[name]
            t = open(tp, encoding="utf-8").read()
            open(tp, "w", encoding="utf-8", newline="\n").write(apply(t, name, rel, "docs", "final"))
            print("template", tp)


if __name__ == "__main__":
    main()
