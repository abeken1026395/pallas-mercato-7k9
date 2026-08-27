# -*- coding: utf-8 -*-
"""検証03（F持ちのイン）: results/ だけを読み docs/kensho/fmochi/index.html を生成する。

正本は scripts/templateFmochi.html。生成物を直接編集しないこと。
外部ネットワークに出ない。リポジトリ内の results/*.json のみを読む。

記事本文の数値は外部の成績原簿（2021-11-01〜）で確定させた凍結値でテンプレに直書きされている。
このスクリプトが毎日書き換えるのは「検証データ欄」と本文中の成立条件ブロックだけで、
results/ にある期間だけを使って同じ向きが出続けているかを判定する。
"""
import datetime
import glob
import json
import os
import re
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(ROOT, "scripts", "templateFmochi.html")
OUT = os.path.join(ROOT, "docs", "kensho", "fmochi", "index.html")

F_CODE = 14          # results の「着」= フライング
ABSENT = 16          # 欠場。分母から除く
MIN_F0 = 10          # 個体内比較でF0側に必要な走数
MIN_TGT = 3          # 個体内比較で対象側に必要な走数
N_GROUP = 200        # 群間を判定してよい最小の枠数
N_INDIV = 20         # 個体内を判定してよい最小の人数


def period_key(hd):
    """期は5/1と11/1で切り替わる。その期の識別子を返す。"""
    y, md = hd[:4], hd[4:]
    return (y, "A") if "0501" <= md < "1101" else ((y, "B") if md >= "1101" else (str(int(y) - 1), "B"))


def collect():
    files = sorted(glob.glob(os.path.join(ROOT, "results", "20*.json")))
    if not files:
        raise SystemExit("fmochi: results/ が見つかりません")

    # 期の途中から数え始めると累積F本数が不正確になる。最初の期の切り替わり以降だけを使う。
    days = [os.path.basename(p)[:8] for p in files]
    first = days[0] if days[0][4:] in ("0501", "1101") else None
    if first is None:
        for a, b in zip(days, days[1:]):
            if period_key(a) != period_key(b):
                first = b
                break
    if first is None:
        raise SystemExit("fmochi: 期の切り替わりを含む期間がありません")

    fcnt = defaultdict(int)
    cur = None
    rows = []          # (登番, F本数, ST, 着)
    ever_f = set()
    n_days = 0
    races = set()
    for path in files:
        hd = os.path.basename(path)[:8]
        if hd < first:
            continue
        pk = period_key(hd)
        if pk != cur:
            fcnt = defaultdict(int)
            cur = pk
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        n_days += 1
        today_f = []
        for r in d.get("結果", []):
            races.add((hd, r.get("場コード"), r.get("レース")))
            for b in r.get("艇", []):
                ch = b.get("着")
                no = b.get("登番")
                st = b.get("ST")
                if b.get("コース") == 1 and no is not None and ch is not None \
                        and ch != ABSENT and isinstance(st, (int, float)):
                    rows.append((no, min(fcnt[no], 2), st, ch))
                if ch == F_CODE and no is not None:
                    today_f.append(no)
                    ever_f.add(no)
        for no in today_f:
            fcnt[no] += 1
    return {"rows": rows, "ever_f": ever_f, "first": first, "last": days[-1],
            "n_days": n_days, "n_races": len(races)}


def analyze(c):
    rows = c["rows"]
    grp = {}
    for f in (0, 1, 2):
        g = [r for r in rows if r[1] == f]
        grp[f] = {
            "n": len(g),
            "st": (sum(r[2] for r in g) / len(g)) if g else 0.0,
            "win": (sum(1 for r in g if r[3] == 1) / len(g) * 100) if g else 0.0,
        }

    by = defaultdict(lambda: defaultdict(list))
    for no, f, st, ch in rows:
        by[no][f].append(st)
    indiv = {}
    for tgt in (1, 2):
        diffs = []
        for no, m in by.items():
            if len(m.get(0, [])) >= MIN_F0 and len(m.get(tgt, [])) >= MIN_TGT:
                base = sum(m[0]) / len(m[0])
                after = sum(m[tgt]) / len(m[tgt])
                diffs.append(after - base)
        indiv[tgt] = {
            "n": len(diffs),
            "diff": (sum(diffs) / len(diffs)) if diffs else 0.0,
            "slow": (sum(1 for x in diffs if x > 0) / len(diffs) * 100) if diffs else 0.0,
        }

    f0_by = {no: v[0] for no, v in by.items() if len(v.get(0, [])) >= MIN_F0}
    a = [sum(v) / len(v) for no, v in f0_by.items() if no in c["ever_f"]]
    b = [sum(v) / len(v) for no, v in f0_by.items() if no not in c["ever_f"]]
    exp = {
        "n_ever": len(a), "st_ever": (sum(a) / len(a)) if a else 0.0,
        "n_never": len(b), "st_never": (sum(b) / len(b)) if b else 0.0,
    }
    return {"grp": grp, "indiv": indiv, "exp": exp}


def comma(n):
    return "{:,}".format(int(n))


def render(c, a):
    g, iv, ex = a["grp"], a["indiv"], a["exp"]
    ok_f2 = g[2]["n"] >= N_GROUP and iv[2]["n"] >= N_INDIV

    # (記事の文, 条件, 現在, 状態)  状態は "ok" / "ng" / "na"
    conds = [
        ("F持ちのSTは遅い側にある", "F1の平均STがF0より遅い",
         "%.4f / %.4f" % (g[0]["st"], g[1]["st"]),
         "ok" if g[1]["st"] > g[0]["st"] else "ng"),
        ("同じ選手の中でも遅くなる", "F0→F1で遅くなった選手が半数を超える",
         "%.1f%%（%s人）" % (iv[1]["slow"], comma(iv[1]["n"])),
         ("ok" if iv[1]["slow"] > 50 else "ng") if iv[1]["n"] >= N_INDIV else "na"),
        ("速い選手が切っている", "Fありの選手のF0時STが、Fなしの選手より速い",
         "%.4f / %.4f" % (ex["st_ever"], ex["st_never"]),
         "ok" if ex["st_ever"] < ex["st_never"] else "ng"),
        ("1着率もF0のほうが高い", "F0の1着率がF1を上回る",
         "%.1f%% / %.1f%%" % (g[0]["win"], g[1]["win"]),
         "ok" if g[0]["win"] > g[1]["win"] else "ng"),
        ("F2は、この欄では判定しない",
         "F2の枠が%s以上、かつ個体内が%d人以上" % (comma(N_GROUP), N_INDIV),
         "%s枠 / %s人" % (comma(g[2]["n"]), comma(iv[2]["n"])),
         "ok" if ok_f2 else "na"),
    ]

    v = {}
    v["n_days"] = comma(c["n_days"])
    v["n_races"] = comma(c["n_races"])
    v["n_f0"] = comma(g[0]["n"])
    v["n_f1"] = comma(g[1]["n"])
    v["n_f2"] = comma(g[2]["n"])
    v["st_f0"] = "%.4f" % g[0]["st"]
    v["st_f1"] = "%.4f" % g[1]["st"]
    v["win_f0"] = "%.1f" % g[0]["win"]
    v["win_f1"] = "%.1f" % g[1]["win"]
    v["iv_n"] = comma(iv[1]["n"])
    v["iv_diff"] = "%+.4f" % iv[1]["diff"]
    v["iv_slow"] = "%.1f" % iv[1]["slow"]
    v["iv2_n"] = comma(iv[2]["n"])
    v["ex_ever"] = "%.4f" % ex["st_ever"]
    v["ex_never"] = "%.4f" % ex["st_never"]
    v["n_ever"] = comma(ex["n_ever"])
    v["n_never"] = comma(ex["n_never"])
    for key, idx in (("st_group", 0), ("st_indiv", 1), ("st_exp", 2),
                     ("st_win", 3), ("st_f2", 4)):
        v[key] = {"ok": "✓ 成立", "ng": "✗ 不成立", "na": "— 判定なし"}[conds[idx][3]]

    def fmt_day(hd):
        return "%d/%d/%d" % (int(hd[:4]), int(hd[4:6]), int(hd[6:]))

    v["period"] = "%s 〜 %s" % (fmt_day(c["first"]), fmt_day(c["last"]))
    v["updated"] = datetime.datetime.now().strftime("%Y/%m/%d")

    rows = []
    for text, cond, now, state in conds:
        mark = {"ok": "✓", "ng": "✗", "na": "—"}[state]
        rows.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
                    % (text, cond, now, mark))
    cond_tb = "".join(rows)

    rows = []
    for label, f in (("F0", 0), ("F1", 1), ("F2", 2)):
        cls = ' class="hi"' if f == 2 else ""
        rows.append("<tr%s><td>%s</td><td>%s</td><td>%.4f</td><td>%.1f%%</td></tr>"
                    % (cls, label, comma(g[f]["n"]), g[f]["st"], g[f]["win"]))
    group_tb = "".join(rows)

    scale_tb = "".join([
        "<tr><td>数えた日数</td><td>%s</td></tr>" % comma(c["n_days"]),
        "<tr><td>数えたレース</td><td>%s</td></tr>" % comma(c["n_races"]),
        "<tr><td>1コースの枠</td><td>%s</td></tr>" % comma(len(c["rows"])),
        "<tr><td>個体内で比べた選手（F1）</td><td>%s</td></tr>" % comma(iv[1]["n"]),
        "<tr><td>個体内で比べた選手（F2）</td><td>%s</td></tr>" % comma(iv[2]["n"]),
        "<tr><td>Fを切った選手</td><td>%s</td></tr>" % comma(ex["n_ever"]),
        "<tr><td>一度も切っていない選手</td><td>%s</td></tr>" % comma(ex["n_never"]),
    ])

    t = {"cond": cond_tb, "group": group_tb, "scale": scale_tb}
    return v, t


def inject(html, v, t):
    for k, val in v.items():
        html = re.sub(r'(<[^>]*data-v="%s"[^>]*>)[^<]*(</)' % re.escape(k),
                      lambda m: m.group(1) + val + m.group(2), html)
    for k, val in t.items():
        html = re.sub(r'(<tbody data-t="%s">)(</tbody>)' % re.escape(k),
                      lambda m: m.group(1) + val + m.group(2), html)
    for k in ("st_group", "st_indiv", "st_exp", "st_win", "st_f2"):
        cls = {"✓": "ok", "✗": "ng", "—": "na"}[v[k][0]]
        html = html.replace('class="st ok" data-v="%s"' % k, 'class="st %s"' % cls)
    html = re.sub(r'\s+data-[vt]="[^"]*"', "", html)
    return html


def main():
    c = collect()
    a = analyze(c)
    v, t = render(c, a)
    with open(TEMPLATE, encoding="utf-8") as f:
        html = f.read()
    out = inject(html, v, t)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    prevtxt = ""
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as f:
            prevtxt = f.read()

    def strip_date(s):
        return re.sub(r"最終更新 <span>[^<]*</span>", "最終更新 <span></span>", s)

    if prevtxt and strip_date(prevtxt) == strip_date(out):
        print("fmochi: no change (skip write)")
        return
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(out)
    print("fmochi: wrote %d bytes / days %s / races %s / f1 %s / f2 %s / indiv %s"
          % (len(out.encode()), comma(c["n_days"]), comma(c["n_races"]),
             comma(a["grp"][1]["n"]), comma(a["grp"][2]["n"]), comma(a["indiv"][1]["n"])))


if __name__ == "__main__":
    main()
