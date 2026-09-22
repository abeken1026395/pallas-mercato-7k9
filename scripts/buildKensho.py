# -*- coding: utf-8 -*-
"""
docs/kensho/shobugake/index.html を生成する。

正本は scripts/templateKensho.html。記事の文章はそこにあり、
このスクリプトは数字だけを差し込む。文章は絶対に触らない。

【毎日更新するもの】
  ・準優の答え合わせ（直近14日）
  ・再現率の推移（月別）
  ・最終更新日

【固定値】
  記事本文の数字は 2016/11/1〜2026/8/31 の10年集計（ローカルのKファイル）で、テンプレートに直書き。
  このスクリプトは本文の数字を差し込まない。

【累積ファイル】
  data/kenshoVerify.json（gitignore）に節ごとの答え合わせ結果を貯める。
  既に計算済みの節は再計算しない。

【外部アクセス】
  BoatraceOpenAPI/programs のみ。準優の判定に race_subtitle が要るため。
  取得済みの日は data/programsCache/ から読む（gitignore）。
"""
import json, os, sys, re, glob, collections, datetime, urllib.request, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(ROOT, "scripts", "templateKensho.html")
OUT = os.path.join(ROOT, "docs", "kensho", "shobugake", "index.html")
RESULTS = os.path.join(ROOT, "results")
DATA = os.path.join(ROOT, "data")
CACHE = os.path.join(DATA, "programsCache")
VERIFY = os.path.join(DATA, "kenshoVerify.json")

# 何日ぶんの programs を見るか。節の復元には節全体が要るので余裕を持つ。
SCAN_DAYS = 45
# 答え合わせ欄に載せる日数
SHOW_DAYS = 14

PTS = {1: 10, 2: 8, 3: 6, 4: 4, 5: 2, 6: 1}
GB = {1: 2, 2: 1, 3: 1, 4: 0, 5: 0}
EXCL = {7, 14}  # 7=妨害 14=F → 賞典除外。順位から外す
SPECIAL = ["特選", "特賞", "選抜", "ドリーム"]

VN = {1:"桐生",2:"戸田",3:"江戸川",4:"平和島",5:"多摩川",6:"浜名湖",7:"蒲郡",8:"常滑",
      9:"津",10:"三国",11:"びわこ",12:"住之江",13:"尼崎",14:"鳴門",15:"丸亀",16:"児島",
      17:"宮島",18:"徳山",19:"下関",20:"若松",21:"芦屋",22:"福岡",23:"唐津",24:"大村"}



def prev(d):
    return (datetime.datetime.strptime(d, "%Y%m%d") - datetime.timedelta(days=1)).strftime("%Y%m%d")


def fetch_programs(day):
    """programs を1日分取る。キャッシュがあればそれを返す。"""
    os.makedirs(CACHE, exist_ok=True)
    p = os.path.join(CACHE, day + ".json")
    if os.path.exists(p):
        try:
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    url = ("https://raw.githubusercontent.com/BoatraceOpenAPI/programs/HEAD/docs/v2/%s/%s.json"
           % (day[:4], day))
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "data-seme/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read().decode("utf-8")
    except Exception as e:
        print("programs miss", day, e)
        return None
    with open(p, "w", encoding="utf-8") as f:
        f.write(body)
    time.sleep(0.3)
    try:
        return json.loads(body)
    except Exception:
        return None


def load_days():
    """直近 SCAN_DAYS 日の programs と results を読み、(day,venue)->races にする。"""
    days = sorted(os.path.basename(x)[:8] for x in glob.glob(os.path.join(RESULTS, "*.json")))
    days = days[-SCAN_DAYS:]
    P = collections.defaultdict(dict)
    T = {}
    for d in days:
        pr = fetch_programs(d)
        if not pr:
            continue
        for r in pr.get("programs", []):
            v = r["race_stadium_number"]
            P[(d, v)][r["race_number"]] = {
                "st": r.get("race_subtitle") or "",
                "gr": r.get("race_grade_number"),
                "ent": [(b["racer_number"], b["racer_boat_number"]) for b in r.get("boats", [])],
            }
            T[(d, v)] = r.get("race_title") or ""
        with open(os.path.join(RESULTS, d + ".json"), encoding="utf-8") as f:
            rs = json.load(f)
        for r in rs.get("結果", []):
            v = int(r["場コード"])
            rn = int(str(r["レース"]).replace("R", ""))
            if (d, v) in P and rn in P[(d, v)]:
                P[(d, v)][rn]["chaku"] = {b["登番"]: b.get("着") for b in r.get("艇", [])}
    return days, P, T


def bonus(r):
    return GB.get(r.get("gr"), 0) + (1 if any(k in r["st"] for k in SPECIAL) else 0)


def build_cases(days, P, T):
    """準優のある (day,venue) を見つけ、答え合わせを1件ずつ作る。"""
    dset = set(days)
    out = []
    for (d, v), races in P.items():
        jun = [r for r in races.values() if "準優" in r["st"]]
        if not jun:
            continue
        ys = []
        c = prev(d)
        while (c, v) in P and T.get((c, v)) == T.get((d, v)):
            ys.append(c)
            c = prev(c)
        if not ys:
            continue
        if c not in dset:
            continue          # 節初日が走査範囲の外。判定できない
        if (c, v) in P:
            continue          # title の変化で誤って切れている
        ys = sorted(ys)
        if any("chaku" not in P[(y, v)][rn] for y in ys for rn in P[(y, v)]):
            continue          # 結果が揃っていない日がある
        actual = set(t for r in jun for t, _ in r["ent"])
        pt = collections.defaultdict(int); n = collections.defaultdict(int)
        one = collections.defaultdict(int); bad = set(); last = {}
        for y in ys:
            for rn in sorted(P[(y, v)]):
                r = P[(y, v)][rn]
                if "準優" in r["st"] or r["st"] == "優勝戦":
                    continue
                ch = r.get("chaku", {})
                for t, _w in r["ent"]:
                    cc = ch.get(t)
                    n[t] += 1
                    last[t] = y
                    if cc in EXCL:
                        bad.add(t)
                    if cc in PTS:
                        pt[t] += PTS[cc] + bonus(r)
                        one[t] += (cc == 1)
        cand = [t for t in n if t not in bad and last.get(t) == ys[-1]]
        if not cand:
            continue
        o = sorted(cand, key=lambda t: (pt[t] / n[t], one[t]), reverse=True)
        k = len(actual)
        calc = set(o[:k])
        out.append({"d": d, "v": v, "vn": VN.get(v, str(v)),
                    "k": k, "hit": len(calc & actual)})
    return out


def merge_verify(new):
    """累積ファイルに追記する。既にある節は上書きしない。"""
    old = []
    if os.path.exists(VERIFY):
        try:
            with open(VERIFY, encoding="utf-8") as f:
                old = json.load(f)
        except Exception:
            old = []
    have = set((x["d"], x["v"]) for x in old)
    added = 0
    for x in new:
        if (x["d"], x["v"]) not in have:
            old.append(x)
            added += 1
    old.sort(key=lambda x: (x["d"], x["v"]))
    os.makedirs(DATA, exist_ok=True)
    with open(VERIFY, "w", encoding="utf-8") as f:
        json.dump(old, f, ensure_ascii=False)
    return old, added


def jdate(s):
    return "%s/%d/%d" % (s[:4], int(s[4:6]), int(s[6:8]))


def render(records):
    # 答え合わせ（直近 SHOW_DAYS 日）
    if records:
        cut = (datetime.datetime.strptime(records[-1]["d"], "%Y%m%d")
               - datetime.timedelta(days=SHOW_DAYS - 1)).strftime("%Y%m%d")
    else:
        cut = "99999999"
    recent = [x for x in records if x["d"] >= cut]
    if recent:
        daily = ""
        for x in reversed(recent):
            miss = x["k"] - x["hit"]
            hi = ' class="hi"' if miss == 0 else ""
            daily += ("<tr%s><td>%s %s</td><td>%d</td><td>%d</td><td>%d</td></tr>"
                      % (hi, jdate(x["d"]), x["vn"], x["k"], x["hit"], miss))
    else:
        daily = '<tr><td colspan="4" style="text-align:left">まだ記録がありません。</td></tr>'

    # 再現率の推移（月別）
    m = collections.OrderedDict()
    for x in records:
        a = m.setdefault(x["d"][:6], [0, 0, 0])
        a[0] += x["hit"]; a[1] += x["k"]; a[2] += 1
    acc = ""
    for k in sorted(m, reverse=True):
        h, t, c = m[k]
        acc += ("<tr><td>%s年%d月</td><td>%d</td><td>%s</td><td>%s</td><td>%.1f%%</td></tr>"
                % (k[:4], int(k[4:]), c, format(t, ","), format(h, ","), h / t * 100))
    if not acc:
        acc = '<tr><td colspan="5" style="text-align:left">まだ記録がありません。</td></tr>'

    v = {"updated": datetime.datetime.now().strftime("%Y/%m/%d")}

    t = {"daily": daily, "acc": acc}
    return v, {}, t


def inject(html, v, b, t):
    for k, val in v.items():
        html = re.sub(r'(<[^>]*data-v="%s"[^>]*>)[^<]*(</)' % re.escape(k),
                      lambda m: m.group(1) + val + m.group(2), html)
    for k, val in b.items():
        if k.startswith("tilt"):
            html = re.sub(r'(data-b="%s" style="height:)[^"]*(")' % re.escape(k),
                          lambda m: m.group(1) + val + m.group(2), html)
        else:
            html = re.sub(r'(data-b="%s" style="width:)[^"]*(")' % re.escape(k),
                          lambda m: m.group(1) + val + m.group(2), html)
    for k, val in t.items():
        html = re.sub(r'(<tbody data-t="%s">)(</tbody>)' % re.escape(k),
                      lambda m: m.group(1) + val + m.group(2), html)
    html = html.replace('<div data-t="daily_detail"></div>', "")
    # 動的スクリプトのブロックを丸ごと外す（guard.js 参照は残る）
    a = html.find("<script>\nvar V = window.KENSHO")
    b2 = html.find('<script src="../../assets/guard.js"')
    if a > 0 and b2 > a:
        html = html[:a] + html[b2:]
    html = re.sub(r'\s+data-[vbt]="[^"]*"', "", html)
    return html


def main():
    days, P, T = load_days()
    cases = build_cases(days, P, T)
    records, added = merge_verify(cases)
    v, b, t = render(records)
    with open(TEMPLATE, encoding="utf-8") as f:
        html = f.read()
    out = inject(html, v, b, t)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    prevtxt = ""
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as f:
            prevtxt = f.read()
    # 最終更新日だけの差なら書かない（無用なコミットを避ける）
    def strip_date(s):
        return re.sub(r'最終更新 <span>[^<]*</span>', '最終更新 <span></span>', s)
    if prevtxt and strip_date(prevtxt) == strip_date(out):
        print("kensho: no change (skip write)")
        return
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(out)
    print("kensho: wrote %d bytes / records %d (+%d)" % (len(out.encode()), len(records), added))


if __name__ == "__main__":
    main()
