import sys, json, copy
sys.path.insert(0, "scripts")
import buildResults as b
hd = sys.argv[1]
blank = [tuple(int(x) for x in t.split(":")) for t in sys.argv[2:]]
data = b.fetch_json(hd)
ref = {(int(r["場コード"]), int(r["レース"][:-1])): r for r in b.to_races(data)}
d2 = copy.deepcopy(data)
for sn, rn in blank:
    res = d2["programs"]["stadiums"][str(sn)]["races"][str(rn)]["result"]
    for k in list(res):
        if k not in ("date", "stadium_number", "race_number"):
            res[k] = None if not isinstance(res[k], dict) else {}
    res["racers"] = {}
    res["payouts"] = {}
print("missing after blank:", b.missing_races(d2))
fb = b.official_fallback(d2, hd, {})
got = {(int(r["場コード"]), int(r["レース"][:-1])): r for r in b.to_races(d2, fb)}
for k in blank:
    a, c = ref.get(k), got.get(k)
    if a is None or c is None:
        print(k, "ref" if a else "noref", "got" if c else "nogot")
        continue
    dif = [x for x in a if a[x] != c.get(x)]
    print(k, "results行の差:", dif if dif else "なし(全項目一致)")
    for x in dif:
        print("   ref", json.dumps(a[x], ensure_ascii=False)[:400])
        print("   got", json.dumps(c[x], ensure_ascii=False)[:400])
