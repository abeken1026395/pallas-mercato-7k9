# -*- coding: utf-8 -*-
"""
成果物の鮮度を横断チェックする（単一障害点の外側からの監視）

このリポジトリの収集は、止まってもエラーにならず「データが更新されなくなるだけ」で
気づけない構造になっている（REFERENCE.md (1) の単一障害点3つ）。
2026-08-02 には、22場の払戻収集が1ヶ月以上止まっていたことが発覚した。
`continue-on-error: true` によりワークフロー一覧は緑で埋まったままだった。

そこで「ワークフローの色」ではなく「成果物」を外から見る。
異常があれば非ゼロを返し、呼び出し側が Issue を起票する。

── 払戻CSVを日数しきい値で見ない理由（2026-08-02 実測）──
「最終 hd が N日以上古い場」で判定すると、非開催が続いている場と区別できない。
全24場・全期間の開催間隔を測ると最大105日（尼崎）、95日（児島）、82日（平和島）。
誤検知しない N（100日超）にすると今回の1ヶ月停止を検出できず、
今回の停止を拾える N（7〜30日）にすると非開催の場を毎回誤検知する。
さらに今回は22/24場の停止で、戸田・唐津は正常に更新され続けていたため、
「全場の最新 hd」を見る大域チェックでも素通りする。

そこでミラーと突合する。直近W日の日別JSONを取得し、
**「ミラーに3連単の払戻があるのに、こちらのCSVに無い日」**を場ごとに検出する。
開催の有無を問わないので、非開催による誤検知が原理的に起きない。

results/ と決まり手CSV は単一の対象で、更新頻度も一定なので日数しきい値で見る。

環境変数:
  WINDOW      … 払戻の突合窓（日）既定 10。基準日の前日から遡る
  TH_RESULTS  … results/ のしきい値（日）既定 3  （毎晩更新）
  TH_KIMARITE … 決まり手CSVのしきい値（日）既定 25（毎月2・16日更新）
  GRACE       … 判定から外す直近日数 既定 1（収集待ちの日を鳴らさないため）
  TODAY       … 'YYYYMMDD' 基準日の上書き（試験用）
  FORCE_ISSUE … 1/true なら合成の異常を1件足す。実データは一切変えない。
                本番の異常を待たずに起票経路を確かめるためのもの（検証用）。

出力:
  標準出力に一覧。GITHUB_OUTPUT があれば stale / count / today を書く。
  異常が1つでもあれば exit 1、無ければ exit 0。
"""
import csv
import datetime
import glob
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

RAW = "https://raw.githubusercontent.com/BoatraceOpenAPI/results/gh-pages/docs/v2/{y}/{ymd}.json"
UA = "Mozilla/5.0 boatrace-data-collector"
SLEEP = 0.2
TIMEOUT = 30

def _int_env(name, default):
    """空文字も既定へ倒す。workflow_dispatch の未入力は '' で渡ってくる。"""
    v = os.environ.get(name, "").strip()
    return int(v) if v else default


WINDOW = _int_env("WINDOW", 10)
# 直近 GRACE 日は判定から外す。前日ぶんは払戻WF（JST 00:20〜02:25）がまだ走っていない
# 時間帯があり、そのまま判定すると「収集される前」を欠落として鳴らしてしまうため。
GRACE = _int_env("GRACE", 1)
TH_RESULTS = _int_env("TH_RESULTS", 3)
TH_KIMARITE = _int_env("TH_KIMARITE", 25)
# 起票経路の検証用。本番の異常を待たずに Issue を1本立てて経路を確かめる。
FORCE_ISSUE = os.environ.get("FORCE_ISSUE", "").strip().lower() in ("1", "true", "yes")

JST = datetime.timezone(datetime.timedelta(hours=9))

JCD = {
    1: "kiryu", 2: "toda", 3: "edogawa", 4: "heiwajima", 5: "tamagawa", 6: "hamanako",
    7: "gamagori", 8: "tokoname", 9: "tsu", 10: "mikuni", 11: "biwako", 12: "suminoe",
    13: "amagasaki", 14: "naruto", 15: "marugame", 16: "kojima", 17: "miyajima",
    18: "tokuyama", 19: "shimonoseki", 20: "wakamatsu", 21: "ashiya", 22: "fukuoka",
    23: "karatsu", 24: "omura",
}


def today_jst():
    s = os.environ.get("TODAY", "").strip()
    if s:
        return datetime.date(int(s[0:4]), int(s[4:6]), int(s[6:8]))
    return datetime.datetime.now(JST).date()


def d(ymd):
    return datetime.date(int(ymd[0:4]), int(ymd[4:6]), int(ymd[6:8]))


def fetch_day(day):
    """その日のv2 JSONを返す。404(非配信)なら None。到達できなければ例外。"""
    url = RAW.format(y=day.strftime("%Y"), ymd=day.strftime("%Y%m%d"))
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8", "ignore"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def csv_days(path):
    """払戻CSVに入っている hd の集合。"""
    out = set()
    with open(path, encoding="utf-8", newline="") as f:
        r = csv.reader(f)
        next(r, None)
        for row in r:
            if row and re.fullmatch(r"\d{8}", row[0]):
                out.add(row[0])
    return out


def check_payouts(today):
    """ミラーと突合し「ミラーにあるのにCSVに無い日」を場ごとに返す。"""
    # 前日までが確定分。さらに GRACE 日ぶん手前で切り、収集待ちの日を鳴らさない。
    end = today - datetime.timedelta(days=1 + GRACE)
    start = end - datetime.timedelta(days=WINDOW - 1)

    expect = {v: set() for v in JCD.values()}
    unreachable = []
    fetched = 0
    day = start
    while day <= end:
        ymd = day.strftime("%Y%m%d")
        try:
            doc = fetch_day(day)
            fetched += 1
        except Exception as e:
            unreachable.append((ymd, repr(e)))
            day += datetime.timedelta(days=1)
            time.sleep(SLEEP)
            continue
        if doc is not None:
            for rec in doc.get("results", []):
                j = rec.get("race_stadium_number")
                tri = (rec.get("payouts") or {}).get("trifecta") or []
                if j not in JCD or not rec.get("race_number") or not tri:
                    continue
                t = tri[0]
                if t.get("combination") and t.get("payout") is not None:
                    expect[JCD[j]].add(ymd)
        day += datetime.timedelta(days=1)
        time.sleep(SLEEP)

    rows = []
    # ミラーに1日も到達できなかった＝ミラー側 or ネットワークの問題。
    # 場ごとの欠落判定は成立しないので行を返さない（到達不可そのものは呼び出し側が異常に数える）。
    if fetched == 0:
        return rows, unreachable, start, end

    window = [(start + datetime.timedelta(days=i)).strftime("%Y%m%d")
              for i in range((end - start).days + 1)]
    for name in sorted(JCD.values()):
        p = "docs/payouts/%sPayouts.csv" % name
        if not os.path.exists(p):
            rows.append((name, "-", "CSVが無い", [], [], []))
            continue
        try:
            have_all = csv_days(p)
        except Exception as e:
            rows.append((name, "-", "CSVが読めない(%r)" % (e,), [], [], []))
            continue
        mirror_days = sorted(expect[name])
        csv_in_window = sorted(x for x in have_all if x in window)
        miss = sorted(expect[name] - have_all)
        last = max(have_all) if have_all else "-"
        st = "欠落%d日" % len(miss) if miss else "OK"
        rows.append((name, last, st, mirror_days, csv_in_window, miss))
    return rows, unreachable, start, end


def check_results(today):
    days = sorted(re.findall(r"(\d{8})\.json", " ".join(glob.glob("results/*.json"))))
    if not days:
        return [("results/", "-", "ファイルなし")]
    hd = days[-1]
    age = (today - d(hd)).days
    return [("results/", hd, "OK" if age <= TH_RESULTS else "古い（%d日前）" % age)]


def check_kimarite(today):
    p = "docs/players/racerKimarite.csv"
    if not os.path.exists(p):
        return [(p, "-", "ファイルなし")]
    last = None
    try:
        with open(p, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                v = (row.get("集計終了") or "").strip()
                if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v) and (last is None or v > last):
                    last = v
    except Exception as e:
        return [(p, "-", "読めない(%r)" % (e,))]
    if last is None:
        return [(p, "-", "集計終了が読めない")]
    age = (today - d(last.replace("-", ""))).days
    return [(p, last, "OK" if age <= TH_KIMARITE else "古い（%d日前）" % age)]


def main():
    today = today_jst()
    print("基準日(JST): %s" % today.strftime("%Y-%m-%d"))

    prows, unreachable, start, end = check_payouts(today)
    win = "%s〜%s（%d日窓）" % (start.strftime("%Y%m%d"), end.strftime("%Y%m%d"), WINDOW)
    print("\n[払戻CSV(24場)] ミラー突合 %s" % win)
    for name, last, st, mir, incsv, miss in prows:
        print("  %-14s 最終 %-10s %s" % (name, last, st))
        if miss:
            print("      ミラーにある日 (%d): %s" % (len(mir), " ".join(mir) or "-"))
            print("      CSVにある日   (%d): %s" % (len(incsv), " ".join(incsv) or "-"))
            print("      欠落          (%d): %s" % (len(miss), " ".join(miss)))
    if unreachable:
        print("  ※ ミラーから取得できなかった日 %d件: %s"
              % (len(unreachable), " ".join(x[0] for x in unreachable)))

    groups = [("results/", check_results(today)), ("決まり手CSV", check_kimarite(today))]
    for title, rows in groups:
        print("\n[%s]" % title)
        for name, last, st in rows:
            print("  %-14s 最終 %-10s %s" % (name, last, st))

    bad = [("払戻CSV", n, l, s) for n, l, s, _m, _c, _x in prows if s != "OK"]
    for title, rows in groups:
        bad += [(title, n, l, s) for n, l, s in rows if s != "OK"]
    # 起票経路の検証。実データは一切変えず、合成の1件だけを足す。
    if FORCE_ISSUE:
        bad.append(("検証", "FORCE_ISSUE", "-", "起票経路の確認用のダミー（実データは正常）"))

    # ミラー到達不可は沈黙させない。1日でも取れなければ異常として数える。
    if unreachable:
        note = "取得できなかった日 %d/%d件" % (len(unreachable), WINDOW)
        if len(unreachable) == WINDOW:
            note += "（全滅。場ごとの欠落判定は成立していない）"
        bad.append(("ミラー", "BoatraceOpenAPI", "-", note))

    print("\n異常な対象: %d件" % len(bad))

    if bad:
        lines = []
        if FORCE_ISSUE:
            lines += ["> **これは FORCE_ISSUE による検証用の起票です。**",
                      "> 起票経路（ラベル作成・本文生成・冪等スキップ）を確認するためのもので、",
                      "> 実データの異常を意味しません。確認後は close してください。", ""]
        lines += ["対象窓: %s" % win, "",
                  "| 区分 | 対象 | 最終 | 状態 |", "|---|---|---|---|"]
        for title, n, l, s in bad:
            lines.append("| %s | `%s` | %s | %s |" % (title, n, l, s))
        det = [(n, mir, incsv, miss) for n, _l, _s, mir, incsv, miss in prows if miss]
        if det:
            lines += ["", "### 欠落の内訳（窓内）", "",
                      "| 場 | ミラーにある日 | CSVにある日 | 欠落 |", "|---|---|---|---|"]
            for n, mir, incsv, miss in det:
                lines.append("| `%s` | %d日<br>%s | %d日<br>%s | **%d日**<br>%s |"
                             % (n, len(mir), " ".join(mir) or "-",
                                len(incsv), " ".join(incsv) or "-",
                                len(miss), " ".join(miss)))
        if unreachable:
            lines += ["", "### ミラーから取得できなかった日", "",
                      "取得成功 %d日 / 失敗 %d日。**「繋がらなかった」は沈黙ではなく異常。**"
                      % (WINDOW - len(unreachable), len(unreachable)), "",
                      "| 日付 | 理由 |", "|---|---|"]
            for ymd, err in unreachable:
                lines.append("| %s | `%s` |" % (ymd, err.replace("|", "\\|")[:120]))
            if all(x[0] for x in unreachable) and len(unreachable) == WINDOW:
                lines += ["", "**窓内の全日に到達できていないため、"
                              "各場の欠落判定は成立していない。**"]
        with open("freshness_summary.md", "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    elif os.path.exists("freshness_summary.md"):
        # 前回の残骸を Issue 本文に使わせない
        os.remove("freshness_summary.md")

    gh = os.environ.get("GITHUB_OUTPUT")
    if gh:
        with open(gh, "a", encoding="utf-8") as f:
            f.write("stale=%d\n" % (1 if bad else 0))
            f.write("count=%d\n" % len(bad))
            f.write("today=%s\n" % today.strftime("%Y%m%d"))
            f.write("forced=%d\n" % (1 if FORCE_ISSUE else 0))

    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
