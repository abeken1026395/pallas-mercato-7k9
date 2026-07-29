# -*- coding: utf-8 -*-
# buildProfileLite.py
# docs/players/profile.json（正本・手入力）から、選手図鑑の一覧カードで使う
# tagline / nickname だけを抜き出した軽量版 docs/players/profileLite.json を作る。
# 一覧の初期表示ではこの軽量版だけを読み、note/hobby を含むフル版は
# 詳細を開いた時に遅延読込する（初期表示の転送量を減らすため）。
# profile.json は読むだけで、書き換えない。
import io
import os
import json

SRC = os.path.join("docs", "players", "profile.json")
OUT = os.path.join("docs", "players", "profileLite.json")

KEYS = ("tagline", "nickname")


def main():
    with io.open(SRC, "r", encoding="utf-8") as f:
        prof = json.load(f)

    lite = {}
    for no, v in prof.items():
        if not isinstance(v, dict):
            continue
        row = {}
        for k in KEYS:
            if v.get(k):
                row[k] = v[k]
        if row:                      # tagline も nickname も無い選手は出力しない
            lite[no] = row

    with io.open(OUT, "w", encoding="utf-8") as f:
        json.dump(lite, f, ensure_ascii=False, separators=(",", ":"))

    print("wrote", OUT, len(lite), "players (from", len(prof), "in", SRC + ")")


if __name__ == "__main__":
    main()
