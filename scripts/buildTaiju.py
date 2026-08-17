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
MIN_RIDES = 10
MIN_W = {"M": 52.0, "F": 47.0}
BANDS = ["未満（錘）", "+0.0〜0.4", "+0.5〜0.9", "+1.0〜1.9", "+2.0〜3.9", "+4.0以上"]
SD_LIMIT = 0.5
ST_LIMIT = 0.005
HIST_LO = -1.0
HIST_HI = 1.0


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
    w_by = defaultdict(list)
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
                w_by[b["登番"]].append(w)
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
        "day_w": day_w, "day_p": day_p, "day_st": day_st, "w_by": w_by,
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
    n_obs = setsu_n = setsu_rides = 0
    by_sex = {"M": [0.0, 0.0, 0], "F": [0.0, 0.0, 0]}
    per_racer = defaultdict(list)

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
            per_racer[toban].append((g[0], mw))
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

    gap_all = []
    gap_bins = {"2週間以内": [], "1か月半まで": [], "それ以上": []}
    for toban, lst in per_racer.items():
        lst.sort()
        for (d1, v1), (d2, v2) in zip(lst, lst[1:]):
            diff = abs(v2 - v1)
            gap_all.append(diff)
            span = (to_date(d2) - to_date(d1)).days
            if span <= 14:
                gap_bins["2週間以内"].append(diff)
            elif span <= 45:
                gap_bins["1か月半まで"].append(diff)
            else:
                gap_bins["それ以上"].append(diff)

    med = {t: statistics.median(v) for t, v in c["w_by"].items() if len(v) >= MIN_RIDES}
    band_ct = {s: Counter() for s in ("M", "F")}
    sex_vals = {"M": [], "F": []}
    for toban, v in med.items():
        sex = "F" if toban in female else "M"
        sex_vals[sex].append(v)
        d = v - MIN_W[sex]
        if d < 0:
            band_ct[sex][BANDS[0]] += 1
        elif d < 0.5:
            band_ct[sex][BANDS[1]] += 1
        elif d < 1.0:
            band_ct[sex][BANDS[2]] += 1
        elif d < 2.0:
            band_ct[sex][BANDS[3]] += 1
        elif d < 4.0:
            band_ct[sex][BANDS[4]] += 1
        else:
            band_ct[sex][BANDS[5]] += 1

    hist = Counter()
    for v in sex_vals["M"]:
        d = round(v - MIN_W["M"], 1)
        if HIST_LO <= d <= HIST_HI:
            hist[round(MIN_W["M"] + d, 1)] += 1
    peak_w, peak_n = (hist.most_common(1)[0] if hist else (0.0, 0))
    rest = [n for w, n in hist.items() if w != peak_w]
    second = max(rest) if rest else 0

    sd_w = statistics.pstdev(devs) if devs else 0.0
    coef_pt = sxy / sxx if sxx else 0.0
    coef_st = st_sxy / st_sxx if st_sxx else 0.0
    return {
        "curve": {(s, i): (statistics.mean(v), len(v)) for (s, i), v in curve.items() if v},
        "sd_w": sd_w,
        "coef_pt": coef_pt,
        "coef_st": coef_st,
        "eff_pt": abs(coef_pt) * sd_w,
        "eff_st": abs(coef_st) * sd_w,
        "pt_sd": statistics.pstdev(pts) if pts else 0.0,
        "n_setsu": setsu_n,
        "n_setsu_rides": setsu_rides,
        "n_obs": n_obs,
        "gap_med": statistics.median(gap_all) if gap_all else 0.0,
        "gap_n": len(gap_all),
        "gap_over": (sum(1 for x in gap_all if x >= SD_LIMIT) / len(gap_all)) if gap_all else 0.0,
        "gap_bins": {k: (statistics.median(v), len(v)) for k, v in gap_bins.items() if v},
        "band": band_ct,
        "n_racers": len(med),
        "n_m": len(sex_vals["M"]),
        "med_m": statistics.median(sex_vals["M"]) if sex_vals["M"] else 0.0,
        "med_f": statistics.median(sex_vals["F"]) if sex_vals["F"] else 0.0,
        "hist": dict(hist),
        "peak_w": peak_w,
        "peak_n": peak_n,
        "second_n": second,
    }


def fmt_kg(x):
    return ("−" if x < 0 else "+") + "%.2f" % abs(x)


def comma(n):
    return "{:,}".format(int(n))


def render(c, a):
    m3 = a["curve"].get(("M", 2), (0.0, 0))[0]
    m6 = a["curve"].get(("M", 5), (0.0, 0))[0]
    peak_ok = abs(a["peak_w"] - MIN_W["M"]) < 0.05
    conds = [
        ("落ちるのは2日目まで", "6日目が3日目より深くない", "%s / %s" % (fmt_kg(m3), fmt_kg(m6)),
         m6 >= m3),
        ("軽い日のほうが着は悪い", "節内の係数が負でない", "%+.3f" % a["coef_pt"],
         a["coef_pt"] >= 0),
        ("スタートの桁に届かない", "実効差が0.005秒未満", "%.4f秒" % a["eff_st"],
         a["eff_st"] < ST_LIMIT),
        ("錘の最小の一枚より軽い", "体重の幅が0.5キロ未満", "%.2fキロ" % a["sd_w"],
         a["sd_w"] < SD_LIMIT),
        ("そこに合わせている", "最頻の体重が52.0キロ", "%.1fキロ" % a["peak_w"], peak_ok),
    ]

    near_m = 0
    tot_m = sum(a["band"]["M"].values()) or 1
    near_m = a["band"]["M"][BANDS[1]] / tot_m * 100

    v = {}
    v["n_days"] = comma(len(c["days"]))
    v["n_races"] = comma(c["n_races"])
    v["n_rides"] = comma(a["n_setsu_rides"])
    v["n_setsu"] = comma(a["n_setsu"])
    for i in range(1, 6):
        v["c%d" % (i + 1)] = fmt_kg(a["curve"].get(("M", i), (0.0, 0))[0])
    v["coef_pt"] = "%+.3f" % a["coef_pt"]
    v["coef_st"] = "%.3f" % abs(a["coef_st"])
    v["eff_pt"] = "%.2f" % a["eff_pt"]
    v["eff_ratio"] = comma(round(2.0 / a["eff_pt"])) if a["eff_pt"] > 0 else "—"
    v["eff_st"] = "%.4f" % a["eff_st"]
    v["sd_w"] = "%.2f" % a["sd_w"]
    v["gap_med"] = "%.2f" % a["gap_med"]
    v["gap_over"] = comma(round(1 / a["gap_over"])) if a["gap_over"] > 0 else "—"
    for i, k in enumerate(("2週間以内", "1か月半まで", "それ以上"), start=1):
        v["g%d" % i] = "%.2f" % a["gap_bins"].get(k, (0.0, 0))[0]
    v["n_racers"] = comma(a["n_racers"])
    v["n_m"] = comma(a["n_m"])
    v["med_m"] = "%.2f" % a["med_m"]
    v["med_f"] = "%.1f" % a["med_f"]
    v["gap_m"] = "%.2f" % (a["med_m"] - MIN_W["M"])
    v["peak_w"] = "%.1f" % a["peak_w"]
    v["peak_n"] = comma(a["peak_n"])
    v["peak_ratio"] = comma(int(a["peak_n"] // a["second_n"])) if a["second_n"] else "—"
    v["near_m"] = "%.0f" % near_m
    tm = c["adj_tot"]["M"] or 1
    tf = c["adj_tot"]["F"] or 1
    v["w_m"] = "%.1f%%" % (c["adj_hit"]["M"] / tm * 100)
    v["w_f"] = "%.1f%%" % (c["adj_hit"]["F"] / tf * 100)
    for key, idx in (("st_curve", 0), ("st_coef", 1), ("st_st", 2), ("st_sd", 3), ("st_peak", 4)):
        v[key] = "✓ 成立" if conds[idx][3] else "✗ 不成立"
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
    gmx = max((x for x, _ in a["gap_bins"].values()), default=0.0)
    for i, k in enumerate(("2週間以内", "1か月半まで", "それ以上"), start=1):
        val = a["gap_bins"].get(k, (0.0, 0))[0]
        b["g%d" % i] = "%.0f%%" % (val / gmx * 100 if gmx else 0)
    b["wm"] = "%.1f%%" % (c["adj_hit"]["M"] / tm * 100)
    b["wf"] = "%.1f%%" % (c["adj_hit"]["F"] / tf * 100)

    rows = []
    for i in range(6):
        mm = a["curve"].get(("M", i))
        ff = a["curve"].get(("F", i))
        if not mm and not ff:
            continue
        rows.append("<tr><td>%d日目</td><td>%s</td><td>%s</td></tr>" % (
            i + 1, fmt_kg(mm[0]) if mm else "—", fmt_kg(ff[0]) if ff else "—"))
    curve_tb = "".join(rows)

    tot_f = sum(a["band"]["F"].values()) or 1
    rows = []
    for bd in BANDS:
        nm = a["band"]["M"][bd]
        nf = a["band"]["F"][bd]
        cls = ' class="hi"' if bd == BANDS[1] else ""
        rows.append("<tr%s><td>%s</td><td>%s (%.1f%%)</td><td>%s (%.1f%%)</td></tr>" % (
            cls, bd, comma(nm), nm / tot_m * 100, comma(nf), nf / tot_f * 100))
    band_tb = "".join(rows)

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
        "<tr><td>続けて出た節の組</td><td>%s</td></tr>" % comma(a["gap_n"]),
        "<tr><td>体重を出した選手</td><td>%s</td></tr>" % comma(a["n_racers"]),
    ])

    rows = []
    hmax = max(a["hist"].values()) if a["hist"] else 1
    for w in sorted(a["hist"]):
        n = a["hist"][w]
        if n * 100.0 / (a["n_m"] or 1) < 1.0 and abs(w - a["peak_w"]) > 0.05:
            continue
        peak = abs(w - a["peak_w"]) < 0.05
        rows.append(
            '<div class="row%s"><span class="kgl">%.1f</span>'
            '<span class="track"><span class="fill" style="width:%.0f%%"></span></span>'
            '<span class="n">%s人</span></div>' % (
                " peak" if peak else "", w, n / hmax * 100, comma(n)))
    rows.append('<p class="cap">男子%s人の体重（中央値）。最低体重52.0キロの前後1キロだけを表示</p>'
                % comma(a["n_m"]))
    hist_fig = "".join(rows)

    t = {"curve": curve_tb, "band": band_tb, "adj": adj_tb, "cond": cond_tb, "scale": scale_tb}
    return v, b, t, hist_fig


def inject(html, v, b, t, hist_fig):
    for k, val in v.items():
        html = re.sub(r'(<[^>]*data-v="%s"[^>]*>)[^<]*(</)' % re.escape(k),
                      lambda m: m.group(1) + val + m.group(2), html)
    for k, val in b.items():
        html = re.sub(r'(data-b="%s" style="width:)[^"]*(")' % re.escape(k),
                      lambda m: m.group(1) + val + m.group(2), html)
    for k, val in t.items():
        html = re.sub(r'(<tbody data-t="%s">)(</tbody>)' % re.escape(k),
                      lambda m: m.group(1) + val + m.group(2), html)
    html = html.replace('<div class="histfig" data-t="hist"></div>',
                        '<div class="histfig">' + hist_fig + '</div>')
    for k in ("st_curve", "st_coef", "st_st", "st_sd", "st_peak"):
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
    v, b, t, hist_fig = render(c, a)
    with open(TEMPLATE, encoding="utf-8") as f:
        html = f.read()
    out = inject(html, v, b, t, hist_fig)
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
    print("taiju: wrote %d bytes / setsu %s / races %s / racers %s / peak %.1fkg %s"
          % (len(out.encode()), comma(a["n_setsu"]), comma(c["n_races"]),
             comma(a["n_racers"]), a["peak_w"], comma(a["peak_n"])))


if __name__ == "__main__":
    main()
