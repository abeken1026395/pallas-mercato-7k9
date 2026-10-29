import sys, json, os, glob
sys.path.insert(0, sys.argv[1])
import buildResults as b
v1 = json.load(open(sys.argv[2])) if len(sys.argv) > 2 and os.path.exists(sys.argv[2]) else None
for f in sorted(glob.glob(os.path.join(sys.argv[3], "*.html"))):
    hd, jcd, rno = os.path.basename(f)[:-5].split("_")
    r = b.parse_official(open(f, encoding="utf-8").read(), hd, jcd, rno)
    print("==", hd, jcd, rno, "->", "None" if r is None else "parsed")
    if r is None:
        continue
    print("  技", r["technique_number_source"], r["technique_number"], "天候", r["weather_number_source"], r["weather_number"],
          "風", r["wind_speed"], r["wind_direction_number"], "波", r["wave_height"], "気温", r["air_temperature"], "水温", r["water_temperature"])
    for en in sorted(r["racers"]):
        x = r["racers"][en]
        print("  枠%s 着%s(%s) コース%s ST%s(%s) %s %s" % (en, x["place_number"], x["place_number_source"], x["course_number"],
              x["start_timing"], x["start_timing_source"], x["number"], x["name"]))
    for k, rows in r["payouts"].items():
        print("  ", k, rows)
    if v1:
        o = ((v1["programs"]["stadiums"].get(str(int(jcd))) or {}).get("races") or {}).get(str(int(rno)), {}).get("result")
        if not o:
            print("  v1: なし"); continue
        diff = []
        for k in ["wind_speed", "wind_direction_number", "wave_height", "weather_number", "air_temperature",
                  "water_temperature", "technique_number"]:
            if o.get(k) != r.get(k): diff.append((k, o.get(k), r.get(k)))
        for en, ob in o["racers"].items():
            rb = r["racers"].get(en) or {}
            for k in ["entry_number", "course_number", "start_timing", "place_number", "number", "name",
                      "start_timing_source", "place_number_source"]:
                if ob.get(k) != rb.get(k): diff.append((en, k, ob.get(k), rb.get(k)))
        for k, rows in o["payouts"].items():
            a = [(e["combination"], e["amount"]) for e in rows]
            c = [(e["combination"], e["amount"]) for e in r["payouts"].get(k, [])]
            if sorted(a) != sorted(c): diff.append((k, a, c))
        print("  v1との差:", diff if diff else "なし(全項目一致)")
