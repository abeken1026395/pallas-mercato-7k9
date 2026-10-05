"""選手カード：書き出す前の検査。1つでも外れたら build.py は書き出さない。

ページ（senshuCardE.html の tagList・FACTS・WN）と同じ決まりで、選手ごとに出る4つを組み立てて調べる。
ページの決まりを変えたら、ここも同じに直す。
"""
PRI = ["makuri", "maezuke", "tiltDash", "sashi", "nuki", "p23", "geko", "fut", "zst", "kanso", "co1", "co2", "co3", "co4", "co5", "co6"]
WN = {"makuri": ["豪腕まくり", "旋風まくり", "外殻破り"], "maezuke": ["内角強奪", "枠なり破り", "深攻め"],
      "tiltDash": ["チルトダッシュ", "天翔るダッシュ", "天翔るダッシュ"], "sashi": ["針の穴", "針の穴", "影差し"],
      "nuki": ["逆転の舟足", "逆転の舟足", "道中の逆襲"], "p23": ["食らいつき", "食らいつき", "二の矢"],
      "geko": ["下剋上"] * 3, "fut": ["不退転"] * 3, "zst": ["ゼロ台の牙"] * 3, "kanso": ["完全走破"] * 3,
      "co1": ["鉄壁イン"] * 3, "co2": ["二ノ陣"] * 3, "co3": ["三ノ陣"] * 3, "co4": ["四ノ陣"] * 3, "co5": ["五ノ陣"] * 3, "co6": ["大外の意地"] * 3}
FACT = ["覇者の証", "大舞台", "初白星", "駆け上がり", "勝ち星", "初陣", "閃光スタート", "主戦場", "積み重ね"]


def name(k, v):
    return WN[k][v[4] - 1]


def picks(P, W, prior, ay):
    w = P["w"][W]
    avg = {k: a / (a + b) * 100 for k, (a, b) in prior.items()}
    nMin, kMin = (10, 2) if W == "h1" else (20, 3)
    L = [(k, v) for k, v in w.get("tg", {}).items() if v[4] < 3 or (v[2] >= nMin and v[1] >= kMin and v[0] >= avg.get(k, 0))]
    L.sort(key=lambda kv: (kv[1][4], kv[1][3], PRI.index(kv[0]) if kv[0] in PRI else -1))
    items = [("t", name(k, v)) for k, v in L]
    b = ay.get("b", [None] * 4)
    x = ay.get(W)
    yc = P.get("yc", [[0], [0]])
    if yc[0][0] > 0:
        items.append(("f", "覇者の証"))
    if yc[1][0] > 0:
        items.append(("f", "大舞台"))
    if b[3]:
        items.append(("f", "初白星"))
    if b[2]:
        items.append(("f", "駆け上がり"))
    if x and x[2] > 0:
        items.append(("f", "勝ち星"))
    if b[0] or b[1]:
        items.append(("f", "初陣"))
    if x and len(x) > 3 and x[3] <= 0.10:
        items.append(("f", "閃光スタート"))
    if x and x[1] < w["n"]:
        items.append(("f", "主戦場"))
    if w["n"] > 0:
        items.append(("f", "積み重ね"))
    for i, it in enumerate(items):
        if it[1] not in ("不退転", "完全走破"):
            if i > 0:
                items.insert(0, items.pop(i))
            break
    return items[:4]


def run(card, ayumi):
    problems = []
    used = {W: {} for W in ("y1", "h1", "all")}
    short = {W: 0 for W in used}
    for t, P in card["players"].items():
        for W in used:
            w = P["w"].get(W)
            if not w:
                continue
            # 数の整合
            if sum(w["c"]) > w["n"] or sum(c[0] for c in w["co"]) > w["n"]:
                problems.append(f"{t} {W} 着やコース別の数が出走を超える")
            if P["yc"][0][0] > P["yc"][1][0]:
                problems.append(f"{t} 優勝が優出を超える")
            it = picks(P, W, card["win"][W]["tagPrior"], ayumi.get(t, {}))
            if not it:
                problems.append(f"{t} {W} 技も事実も0（何もない選手）")
            if len(it) < 4:
                short[W] += 1
            for _, nm in it:
                used[W][nm] = used[W].get(nm, 0) + 1
    allNames = {n for v in WN.values() for n in v}
    owner = {}
    for k, v in WN.items():
        for n in v:
            owner.setdefault(n, set()).add(k)
    for n, ks in owner.items():
        if len(ks) > 1:
            problems.append(f"技名 {n} が2つの系統に使われている")
    for n in sorted(allNames - set(used["y1"])):
        problems.append(f"直近1年で技名 {n} が誰にも出ない")
    print("4つ未満の選手（参考）", short, "半年で出ない技名（了承済み）", sorted(allNames - set(used["h1"])))
    return problems
