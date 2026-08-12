# -*- coding: utf-8 -*-
"""検証02（体重）: preview/ と results/ を突合し docs/kensho/taiju/index.html を生成する。

正本は scripts/templateTaiju.html。生成物を直接編集しないこと。
外部ネットワークに出ない。リポジトリ内の preview/*.json と results/*.json のみを読む。
"""
import datetime
import glob
import json
import os
import re
import statistics
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(ROOT, "scripts", "templateTaiju.html")
OUT = os.path.join(ROOT, "docs", "kensho", "taiju", "index.html")
CORE = os.path.join(ROOT, "docs", "data", "racerStatsCore.json")

PT = {1: 10, 2: 8, 3: 6, 4: 4, 5: 2, 6: 1}
MIN_SETSU_DAYS = 4
SD_LIMIT = 0.5      # 錘の最小刻み（キロ）
ST_LIMIT = 0.005    # スタートの実効差の上限（秒）


def to_date(hd):
    return datetime.date(int(hd[:4]), int(hd[4:6]), int(hd[6:]))


def load_female():
    with open(CORE, encoding="utf-8") as f:
        core = json.load(f)
    return {int(p["no"]) for p in core["players"] if p.get("female")}


def load_weights():
    wt = {}
    for path in sorted(glob.glob(os.path.join(ROOT, "preview", "20*.json"))):
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        hd = d["開催日"]
        for r in d.get("直前情報", []):
            jcd = int(r["stadium_number"])
            rno = int(r["race_number"])
            for b in r.get("racers", []):
                if b.get("weight") is not None:
                    wt[(hd, jcd, rno, b["entry_number"])] = (b["weight"], b.get("weight_adjustment"))
    return wt


def collect(wt, female):
    day_w = defaultdict(list)
    day_p = defaultdict(list)
    day_st = defaultdict(list)
    adj_dist = Counter()
    adj_hit = defaultdict(int)
    adj_tot = defaultdict(int)
    races = set()
    rides = 0
    days = []
    for path in sorted(glob.glob(os.path.join(ROOT, "results", "20*.json"))):
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        hd = d["開催日"]
        used = False
        for r in d.get("結果", []):
            jcd = int(r["場コード"])
            rno = int(str(r["レース"]).replace("R", ""))
            hit = False
            for b in r.get("艇", []):
                key = (hd, jcd, rno, b["枠"])
                if key not in wt:
                    continue
                hit = True
                rides += 1
                w, adj = wt[key]
                sex = "F" if b["登番"] in female else "M"
                adj_tot[sex] += 1
                if adj is not None:
                    adj_dist[float(adj)] += 1
                    if adj > 0:
                        adj_hit[sex] += 1
                if b["着"] in PT:
                    k = (b["登番"], jcd, hd)
                    day_w[k].append(w)
                    day_p[k].append(PT[b["着"]])
                    if isinstance(b.get("ST"), (int, float)):
                        day_st[k].append(b["ST"])
            if hit:
                races.add((hd, jcd, rno))
                used = True
        if used:
            days.append(hd)
    return {
        "day_w": day_w, "day_p": day_p, "day_st": day_st,
        "adj_dist": adj_dist, "adj_hit": adj_hit, "adj_tot": adj_tot,
        "n_races": len(races), "n_rides": rides, "days": days,
    }


def split_setsu(hds):
    hds = sorted(set(hds))
    groups = [[hds[0]]]
    for a, b in zip(hds, hds[1:]):
        if (to_date(b) - to_date(a)).days == 1:
            groups[-1].append(b)
        else:
            groups.append([b])
    return [g for g in groups if len(g) >= MIN_SETSU_DAYS]


def analyze(c, female):
    day_w, day_p, day_st = c["day_w"], c["day_p"], c["day_st"]
    sched = defaultdict(list)
    for (toban, jcd, hd) in day_w:
        sched[(toban, jcd)].append(hd)

    curve = defaultdict(list)
    devs = []
    pts = []
    sxy = sxx = 0.0
    st_sxy = st_sxx = 0.0
    n_obs = st_n = setsu_n = setsu_rides = 0
    by_sex = {"M": [0.0, 0.0, 0], "F": [0.0, 0.0, 0]}

    for (toban, jcd), hds in sched.items():
        sex = "F" if toban in female else "M"
        for g in split_setsu(hds):
            setsu_n += 1
            ws = [statistics.mean(day_w[(toban, jcd, h)]) for h in g]
            ps = [statistics.mean(day_p[(toban, jcd, h)]) for h in g]
            sts = [statistics.mean(day_st[(toban, jcd, h)]) if day_st[(toban, jcd, h)] else None
                   for h in g]
            for h in g:
                setsu_rides += len(day_p[(toban, jcd, h)])
                pts.extend(day_p[(toban, jcd, h)])
            mw = statistics.mean(ws)
            mp = statistics.mean(ps)
            for i, w in enumerate(ws):
                curve[(sex, i)].append(w - ws[0])
            for w, p in zip(ws, ps):
                dx = w - mw
                dy = p - mp
                sxy += dx * dy
                sxx += dx * dx
                n_obs += 1
                devs.append(dx)
                by_sex[sex][0] += dx * dy
                by_sex[sex][1] += dx * dx
                by_sex[sex][2] += 1
            pair = [(w, s) for w, s in zip(ws, sts) if s is not None]
            if len(pair) >= MIN_SETSU_DAYS:
                mws = statistics.mean(w for w, _ in pair)
                mss = statistics.mean(s for _, s in pair)
                for w, s in pair:
                    st_sxy += (w - mws) * (s - mss)
                    st_sxx += (w - mws) ** 2
                    st_n += 1

    sd_w = statistics.pstdev(devs) if devs else 0.0
    coef_pt = sxy / sxx if sxx else 0.0
    coef_st = st_sxy / st_sxx if st_sxx else 0.0
    return {
        "curve": {(s, i): (statistics.mean(v), len(v))
                  for (s, i), v in curve.items() if v},
        "sd_w": sd_w,
        "coef_pt": coef_pt,
        "coef_st": coef_st,
        "coef_m": by_sex["M"][0] / by_sex["M"][1] if by_sex["M"][1] else 0.0,
        "coef_f": by_sex["F"][0] / by_sex["F"][1] if by_sex["F"][1] else 0.0,
        "eff_pt": abs(coef_pt) * sd_w,
        "eff_st": abs(coef_st) * sd_w,
        "pt_sd": statistics.pstdev(pts) if pts else 0.0,
        "n_setsu": setsu_n,
        "n_setsu_rides": setsu_rides,
        "n_obs": n_obs,
    }


def fmt_kg(x):
    return ("−" if x < 0 else "+") + "%.2f" % abs(x)


def comma(n):
    return "{:,}".format(int(n))


def render(c, a):
    m3 = a["curve"].get(("M", 2), (0.0, 0))[0]
    m6 = a["curve"].get(("M", 5), (0.0, 0))[0]
    conds = [
        ("落ちるのは2日目まで", "6日目が3日目より深くない", "%s / %s" % (fmt_kg(m3), fmt_kg(m6)),
         m6 >= m3),
        ("軽い日のほうが着は悪い", "節内の係数が負でない", "%+.3f" % a["coef_pt"],
         a["coef_pt"] >= 0),
        ("スタートの桁に届かない", "実効差が0.005秒未満", "%.4f秒" % a["eff_st"],
         a["eff_st"] < ST_LIMIT),
        ("錘の最小の一枚より軽い", "体重の幅が0.5キロ未満", "%.2fキロ" % a["sd_w"],
         a["sd_w"] < SD_LIMIT),
    ]

    v = {}
    v["n_days"] = comma(len(c["days"]))
    v["n_races"] = comma(c["n_races"])
    v["n_rides"] = comma(a["n_setsu_rides"])
    v["n_setsu"] = comma(a["n_setsu"])
    for i in range(1, 6):
        val = a["curve"].get(("M", i), (0.0, 0))[0]
        v["c%d" % (i + 1)] = fmt_kg(val)
    v["coef_pt"] = "%+.3f" % a["coef_pt"]
    v["coef_st"] = "%.3f" % abs(a["coef_st"])
    v["eff_pt"] = "%.2f" % a["eff_pt"]
    v["eff_ratio"] = comma(round(2.0 / a["eff_pt"])) if a["eff_pt"] > 0 else "—"
    v["eff_st"] = "%.4f" % a["eff_st"]
    v["sd_w"] = "%.2f" % a["sd_w"]
    tot_m = c["adj_tot"]["M"] or 1
    tot_f = c["adj_tot"]["F"] or 1
    v["w_m"] = "%.1f%%" % (c["adj_hit"]["M"] / tot_m * 100)
    v["w_f"] = "%.1f%%" % (c["adj_hit"]["F"] / tot_f * 100)
    v["st_curve"] = "✓ 成立" if conds[0][3] else "✗ 不成立"
    v["st_coef"] = "✓ 成立" if conds[1][3] else "✗ 不成立"
    v["st_st"] = "✓ 成立" if conds[2][3] else "✗ 不成立"
    v["st_sd"] = "✓ 成立" if conds[3][3] else "✗ 不成立"
    days = c["days"]
    v["period"] = "%s 〜 %s" % (to_date(days[0]).strftime("%Y/%-m/%-d"),
                               to_date(days[-1]).strftime("%Y/%-m/%-d")) if days else "—"
    v["updated"] = datetime.datetime.now().strftime("%Y/%m/%d")

    b = {}
    mx = max((abs(a["curve"].get(("M", i), (0.0, 0))[0]) for i in range(1, 6)), default=0.0)
    for i in range(1, 6):
        val = abs(a["curve"].get(("M", i), (0.0, 0))[0])
        b["c%d" % (i + 1)] = "%.0f%%" % (val / mx * 100 if mx else 0)
    b["sd"] = "%.0f%%" % min(a["sd_w"] / SD_LIMIT * 100, 100)
    b["wm"] = "%.1f%%" % (c["adj_hit"]["M"] / tot_m * 100)
    b["wf"] = "%.1f%%" % (c["adj_hit"]["F"] / tot_f * 100)

    rows = []
    for i in range(6):
        mm = a["curve"].get(("M", i))
        ff = a["curve"].get(("F", i))
        if not mm and not ff:
            continue
        rows.append("<tr><td>%d日目</td><td>%s</td><td>%s</td></tr>" % (
            i + 1,
            fmt_kg(mm[0]) if mm else "—",
            fmt_kg(ff[0]) if ff else "—"))
    curve_tb = "".join(rows)

    total_adj = sum(c["adj_dist"].values()) or 1
    rows = []
    for k in sorted(c["adj_dist"]):
        n = c["adj_dist"][k]
        if n * 100.0 / total_adj < 0.05:
            continue
        label = "なし" if k == 0 else "%.1fキロ" % k
        rows.append("<tr%s><td>%s</td><td>%s</td><td>%.1f%%</td></tr>" % (
            ' class="hi"' if k == 0 else "", label, comma(n), n * 100.0 / total_adj))
    adj_tb = "".join(rows)

    rows = []
    for text, cond, now, ok in conds:
        rows.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
            text, cond, now, "✓" if ok else "✗"))
    cond_tb = "".join(rows)

    scale_tb = "".join([
        "<tr><td>突合できたレース</td><td>%s</td></tr>" % comma(c["n_races"]),
        "<tr><td>節（4日以上）</td><td>%s</td></tr>" % comma(a["n_setsu"]),
        "<tr><td>節に含まれる出走</td><td>%s</td></tr>" % comma(a["n_setsu_rides"]),
        "<tr><td>比較に使った日数</td><td>%s</td></tr>" % comma(a["n_obs"]),
    ])

    t = {"curve": curve_tb, "adj": adj_tb, "cond": cond_tb, "scale": scale_tb}
    return v, b, t


def inject(html, v, b, t):
    for k, val in v.items():
        html = re.sub(r'(<[^>]*data-v="%s"[^>]*>)[^<]*(</)' % re.escape(k),
                      lambda m: m.group(1) + val + m.group(2), html)
    for k, val in b.items():
        html = re.sub(r'(data-b="%s" style="width:)[^"]*(")' % re.escape(k),
                      lambda m: m.group(1) + val + m.group(2), html)
    for k, val in t.items():
        html = re.sub(r'(<tbody data-t="%s">)(</tbody>)' % re.escape(k),
                      lambda m: m.group(1) + val + m.group(2), html)
    for k in ("st_curve", "st_coef", "st_st", "st_sd"):
        ok = v[k].startswith("✓")
        html = html.replace('class="st ok" data-v="%s"' % k,
                            'class="st %s"' % ("ok" if ok else "ng"))
    html = re.sub(r'\s+data-[vbt]="[^"]*"', "", html)
    return html


def main():
    female = load_female()
    wt = load_weights()
    if not wt:
        raise SystemExit("taiju: preview/ に体重データが見つかりません")
    c = collect(wt, female)
    if not c["days"]:
        raise SystemExit("taiju: results/ と突合できた日がありません")
    a = analyze(c, female)
    v, b, t = render(c, a)
    with open(TEMPLATE, encoding="utf-8") as f:
        html = f.read()
    out = inject(html, v, b, t)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    prevtxt = ""
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as f:
            prevtxt = f.read()

    def strip_date(s):
        return re.sub(r"最終更新 <span>[^<]*</span>", "最終更新 <span></span>", s)

    if prevtxt and strip_date(prevtxt) == strip_date(out):
        print("taiju: no change (skip write)")
        return
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(out)
    print("taiju: wrote %d bytes / setsu %s / races %s"
          % (len(out.encode()), comma(a["n_setsu"]), comma(c["n_races"])))


if __name__ == "__main__":
    main()
