#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""senshuCommentIndex.py — PCに集めている選手コメント（場の出走表）から、掲載日の分を引く。

選手コメントは PC の C:\\Users\\USER\\senshuComment に毎日集めている（リポジトリの外。公開しない）。
各場が「レース当日の出走表」を前の晩に出し、その中の「選手コメント」欄に前日のレース後の談話が載る。

使い道（2026-10-28 けん裁定）:
  1) 夕方便の素材作り（buildKansenkiSource.py --ready-only）で、選手コメント欄のある場は
     「掲載日の出走表（コメント付き）が取れていること」を書く条件に加える。
     デイの場は早い回、ナイターの場は遅い回に、場ごとに自然に分かれる。
  2) 執筆の直前に、掲載日の分を scripts/logs/commentsFor_<掲載日>.json に書き出し、書き手に渡す。
     scripts/logs/ は .gitignore 済み。コメントの原文はリポジトリにも公開ページにも入れない。

選手コメント欄が無い場（桐生＝記者評のみ 等）と、URL に日付が無く掲載日を特定できない場は対象外。
コメントの置き場が無い環境（GitHub Actions など）では何もしない（条件をかけない）。

使い方:
  python scripts/senshuCommentIndex.py <掲載日YYYYMMDD> [--out <path>]
"""

import io
import json
import os
import re
import sys

ROOT = os.environ.get("SENSHU_COMMENT_ROOT", r"C:\Users\USER\senshuComment")

# 選手コメント欄があり、URL に日付が入っている場（場コード → 集める側のサイト名）。2026-10-28 に実物で確認。
# 1日1ファイル（その日の全レース）に選手コメントが載る場。
COMMENT_SITES = {
    "04": "heiwajima", "06": "hamanako", "07": "gamagori", "08": "tokoname",
    "10": "mikuni", "14": "naruto", "15": "marugame", "16": "kojima",
    "19": "shimonoseki", "20": "wakamatsu", "22": "fukuoka",
}
# レースごとのページ（ajax_yosou.php?targetday=..&race=N）に選手コメントが載る場。PDFは記者の予想文だけなので使わない。
PER_RACE_SITES = {"09": "tsu", "13": "amagasaki"}
# 対象外（2026-10-28 確認）：多摩川・住之江のPDFは記者の予想文・番組表だけ。桐生は記者評のみ。
# 芦屋・唐津・大村・江戸川・徳山・戸田・宮島は URL に日付が無く、掲載日を特定できない。
PER_RACE_MIN = 12


def available(root=ROOT):
    return os.path.isfile(os.path.join(root, "manifest.jsonl"))


def _rows(root):
    out = []
    with io.open(os.path.join(root, "manifest.jsonl"), "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def _texts(root, site, pub8, rows, per_race):
    """掲載日 pub8 のファイルを (種類, 取った時刻, url, 文字のパス, レース番号) で返す。"""
    out = []
    for r in rows:
        if r.get("site") != site or r.get("status") != 200:
            continue
        url = r.get("url") or ""
        if pub8 not in re.findall(r"20\d{6}", url):
            continue
        rn = None
        if per_race:
            m = re.search(r"ajax_yosou\.php\?targetday=\d{8}&race=(\d+)&req=syussou", url)
            if not m:
                continue
            rn = int(m.group(1))
        tp = os.path.join(root, "text", site, (r.get("sha256") or "")[:16] + ".txt")
        if not os.path.isfile(tp):
            continue
        out.append((r.get("type") or "", r.get("fetchedAt") or "", url, tp, rn))
    return out


def _trim_race_page(t):
    """レースごとのページから「選手コメント」の表だけを切り出す（ページ全体は数十KBあり、書き手に渡すには大きすぎる）。"""
    best = -1
    for m in re.finditer("選手コメント", t):
        if "No." in t[m.end():m.end() + 80]:
            best = m.start()
    if best < 0:
        best = t.rfind("選手コメント")
    if best < 0:
        return ""
    end = t.find("モーターの2連対率上位", best)
    end = end if end > 0 else best + 4000
    return t[best:min(end, best + 4000)]


def comment_for(jcd, pub8, root=ROOT, rows=None):
    """掲載日 pub8 の、その場の出走表（コメント付き）を返す。無ければ None。
    1日1ファイルの場：PDF を優先し、新しく取ったものを使う。
    レースごとの場：1Rから12Rまでそろったときだけ、各レースの新しいものを並べて返す。"""
    jcd = str(jcd).zfill(2)
    per_race = jcd in PER_RACE_SITES
    site = PER_RACE_SITES.get(jcd) or COMMENT_SITES.get(jcd)
    if not site or not available(root):
        return None
    rows = rows if rows is not None else _rows(root)
    cands = _texts(root, site, pub8, rows, per_race)
    if not cands:
        return None
    if per_race:
        latest = {}
        for typ, at, url, tp, rn in cands:
            if rn not in latest or at > latest[rn][0]:
                latest[rn] = (at, url, tp)
        if len(latest) < PER_RACE_MIN:
            return None
        rns = sorted(latest)
        return {"site": site, "url": [latest[k][1] for k in rns], "fetchedAt": max(latest[k][0] for k in rns),
                "textPath": [latest[k][2] for k in rns], "races": rns}
    cands.sort(key=lambda c: ((1 if c[0] == "pdf" else 0), c[1]))
    typ, at, url, tp, _ = cands[-1]
    return {"site": site, "url": url, "fetchedAt": at, "textPath": tp}


def missing(jcd, pub8, root=ROOT, rows=None):
    """書く条件として、コメント待ちにすべきなら True。
    コメント欄の無い場・置き場が無い環境では False（条件をかけない）。"""
    j = str(jcd).zfill(2)
    if (j not in COMMENT_SITES and j not in PER_RACE_SITES) or not available(root):
        return False
    return comment_for(jcd, pub8, root, rows) is None


def main():
    args = sys.argv[1:]
    if not args or not re.fullmatch(r"\d{8}", args[0]):
        raise SystemExit("usage: senshuCommentIndex.py <YYYYMMDD> [--out path]")
    pub8 = args[0]
    out_path = args[args.index("--out") + 1] if "--out" in args else None
    doc = {"date": pub8, "note": "各場の出走表の文字（原文）。使ってよいのは「選手コメント」欄だけ。印・予想・記者の評・買い目は使わない。",
           "venues": {}}
    if available():
        rows = _rows(ROOT)
        for jcd in sorted(set(COMMENT_SITES) | set(PER_RACE_SITES)):
            c = comment_for(jcd, pub8, ROOT, rows)
            if not c:
                continue
            paths = c["textPath"] if isinstance(c["textPath"], list) else [c["textPath"]]
            parts = []
            for i, tp in enumerate(paths):
                with io.open(tp, "r", encoding="utf-8", errors="replace") as f:
                    t = f.read()
                parts.append(("【%dR】\n" % c["races"][i] + _trim_race_page(t)) if "races" in c else t)
            doc["venues"][jcd] = {"source": c["url"], "fetchedAt": c["fetchedAt"], "text": "\n\n".join(parts)}
    body = json.dumps(doc, ensure_ascii=False, indent=1)
    if out_path:
        with io.open(out_path, "w", encoding="utf-8") as f:
            f.write(body)
        print("wrote {} ({} venues)".format(out_path, len(doc["venues"])))
    else:
        print(body)


if __name__ == "__main__":
    main()
