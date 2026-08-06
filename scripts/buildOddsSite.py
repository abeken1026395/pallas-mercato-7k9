import json, os, sys

SRC = "odds"
DST = os.path.join("docs", "results", "odds")


def build_day(path):
    with open(path, encoding="utf-8") as f:
        src = json.load(f)
    win = {}
    for r in src.get("オッズ", []):
        jcd = str(r.get("場コード") or "").zfill(2)
        rno = r.get("race_number")
        w = r.get("win")
        if not jcd or not rno or not isinstance(w, dict):
            continue
        row = []
        for i in range(1, 7):
            v = w.get(str(i))
            row.append(v if isinstance(v, (int, float)) else None)
        if all(v is None for v in row):
            continue
        win.setdefault(jcd, {})[str(rno)] = row
    return {
        "開催日": src.get("開催日"),
        "取得時刻": src.get("取得時刻"),
        "注記": src.get("注記"),
        "単勝": win,
    }


def main():
    if not os.path.isdir(SRC):
        print("no src dir")
        return
    os.makedirs(DST, exist_ok=True)
    days = sorted(x for x in os.listdir(SRC) if x.endswith(".json"))
    for name in days:
        out = build_day(os.path.join(SRC, name))
        dst = os.path.join(DST, name)
        new = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
        if os.path.exists(dst):
            with open(dst, encoding="utf-8") as f:
                old = f.read()
            if old == new:
                print("skip", name)
                continue
        with open(dst, "w", encoding="utf-8") as f:
            f.write(new)
        print("write", name, len(new), "bytes")


if __name__ == "__main__":
    main()
