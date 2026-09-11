# -*- coding: utf-8 -*-
"""
updatePayoutsSummary.yml の検算（commit の前に走る）。

4本の集計（summary / trifectaTop / boat1Second / champRace）を1本ずつ検算し、
不合格の出力は HEAD の版に戻して commit に乗せない（未検算・不合格のものを公開しない）。
結果は GITHUB_OUTPUT の checked（検算を終えた本数）/ ng（不合格の本数）で渡す。
ジョブを落とす判断は workflow 最後の集計ステップ（gate）が行う。

不合格にするもの（0件・データ欠損・上流の沈黙を緑にしない）:
  - 生成ステップが success でない（crash・未実行・結果が渡されていない）
  - JSON として開けない
  - 0件 … 場数が24でない / 総レース数（champRace は優勝戦数）が0
  - 欠損 … 累計の総数が HEAD の版より減った（取れたはずの日が抜けた）
  - 沈黙 … 最新日が END（既定＝昨日JST）の前日より古い（summary / trifectaTop / boat1Second）
    根拠（2026-09-10 実測）: 24場の払戻CSVの和集合では、2025-07-13 以降レースの無い日は無い。
    2026-08-01〜09-10 のコミット40本で、最新日の遅れは summary 0日・trifecta/boat1 最大1日。
    champRace は優勝戦が毎日ではない（同期間で最大4日遅れ）ので鮮度は見ず、場数と減少だけ見る。
START/END を手で指定した run は期間が変わるので、場数24と減少の検査は外し、
0件と鮮度（指定 END 基準）だけ見る。

終了コード: 4本の検算を最後まで終えたら 0（不合格があっても 0。判定は ng で渡す）。
検算そのものが完走できなければ非0（workflow 側で commit せず、ジョブを落とす）。
"""
import datetime
import json
import os
import subprocess
import sys

PAYDIR = "docs/payouts"
# (名前, 出力, 生成ステップの outcome を受け取る環境変数, 鮮度を見るか)
TARGETS = [
    ("summary", f"{PAYDIR}/summary.json", "O_SUMMARY", True),
    ("trifectaTop", f"{PAYDIR}/trifectaTop.json", "O_TRIFECTA", True),
    ("boat1Second", f"{PAYDIR}/boat1Second.json", "O_BOAT1", True),
    ("champRace", f"{PAYDIR}/champRace.json", "O_CHAMP", False),
]
VENUES = 24
JST = datetime.timezone(datetime.timedelta(hours=9))


def ymd(s):
    """'2026/09/09' / '20260909' → '20260909'。取れなければ None。"""
    s = (s or "").replace("/", "").strip()
    return s if len(s) == 8 and s.isdigit() else None


def metrics(name, doc):
    """(場数, 累計総数, 最新日YYYYMMDD or None)"""
    if name == "summary":
        return (len(doc.get("arareRanking") or []), int(doc.get("totalRaces") or 0),
                ymd((doc.get("period") or {}).get("to")))
    venues = (doc.get("venues") or {}).values()
    if name == "champRace":
        return len(venues), sum(int(v.get("total") or 0) for v in venues), None
    lasts = [ymd((v.get("period") or {}).get("to")) for v in venues]
    lasts = [x for x in lasts if x]
    return len(venues), sum(int(v.get("races") or 0) for v in venues), (max(lasts) if lasts else None)


def head_doc(path):
    p = subprocess.run(["git", "show", f"HEAD:{path}"], capture_output=True)
    if p.returncode != 0:
        return None
    return json.loads(p.stdout.decode("utf-8"))


def restore(path):
    """不合格の出力を HEAD の版へ戻す（commit に乗せない）。戻せなければ検算未完として落とす。"""
    subprocess.run(["git", "checkout", "HEAD", "--", path], check=True)


def check(name, path, outcome, fresh, end, custom):
    if outcome != "success":
        return [f"生成ステップが success でない（outcome={outcome or '未実行・未受領'}）"]
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except Exception as e:
        return [f"JSON として開けない（{type(e).__name__}: {e}）"]
    vc, total, last = metrics(name, doc)
    ng = []
    if custom:
        if vc == 0:
            ng.append("0件（場数0）")
    elif vc != VENUES:
        ng.append(f"場数 {vc}（{VENUES} でない）")
    if total <= 0:
        ng.append("0件（総数0）")
    if not custom:
        prev = head_doc(path)
        if prev is not None:
            _, ptotal, _ = metrics(name, prev)
            if total < ptotal:
                ng.append(f"累計が減った {ptotal} → {total}（取れたはずの日が欠けている）")
    if fresh:
        limit = (end - datetime.timedelta(days=1)).strftime("%Y%m%d")
        if not last:
            ng.append("最新日が取れない")
        elif last < limit:
            ng.append(f"最新日 {last} が {limit} より古い（上流の沈黙）")
    detail = f"場数{vc} / 総数{total} / 最新日{last or '-'}"
    return ng or [None, detail]


def main():
    start_in = os.environ.get("START", "").strip()
    end_in = os.environ.get("END", "").strip()
    custom = bool(start_in or end_in)
    if end_in:
        end = datetime.datetime.strptime(end_in, "%Y%m%d").date()
    else:
        end = datetime.datetime.now(JST).date() - datetime.timedelta(days=1)
    print(f"検算: END={end.strftime('%Y%m%d')} 期間指定={'あり' if custom else 'なし（既定）'}")

    checked = ng_count = 0
    lines = []
    for name, path, env_key, fresh in TARGETS:
        res = check(name, path, os.environ.get(env_key, "").strip(), fresh, end, custom)
        if res[0] is None:
            line = f"OK  {name}: {res[1]}"
        else:
            ng_count += 1
            restore(path)
            line = f"NG  {name}: {' / '.join(res)} → HEAD の版に戻した（公開しない）"
        print(line)
        lines.append(line)
        checked += 1

    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"checked={checked}\nng={ng_count}\n")
    summ = os.environ.get("GITHUB_STEP_SUMMARY")
    if summ:
        with open(summ, "a", encoding="utf-8") as f:
            f.write("### 払戻集計 検算\n\n" + "\n".join(f"- {x}" for x in lines) + "\n")
    print(f"checked={checked} ng={ng_count}")


if __name__ == "__main__":
    main()
