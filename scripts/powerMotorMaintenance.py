#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
powerMotorMaintenance.py

「短縮秒の個人差は、いつやり直せば決着するか」を出す。

前提:
  - 検定は主系（短縮秒 = (場,日付)正規化）を序盤で残差化したもの。副系は使わない。
  - σ_between = 0.007 秒 を仮定（残差検定の超過分 √(観測−帰無中央値) から）。
    これは「もしこの大きさの個人差が実在するなら」という仮定であって、
    実在の証拠ではない。p=0.25 は未決。

  ※記録: 序盤で残差化すると、選手が系統的に持つ序盤の高さも一緒に落ちる。
    初日から仕上げてくる選手がいるなら、その信号は残差からは消えている。
    今回は「個人差を過小に見る」保守側に効くので結論の向きは歪まないが、
    残差検定が測っているのは「序盤の水準を揃えた上での節内の伸ばし方」だけ。
    序盤そのものの個人差は別途 §5 で見る（実測 p=0.0043・選手間SD 0.0164秒。
    実在する。つまりこの残差化は本物の信号を削っている）。

--- 蓄積後の宿題: 序盤の窓割りを変える -------------------------------------
  現状は「序盤=最初の2日」を共変量に使うため、序盤2日が短縮秒の両側に入り、
  実在する選手成分（0.0164秒）ごと落ちる。

  案: 1日目だけを共変量にし、短縮秒は2日目以降を起点に取る。
      共変量と被説明変数で誤差が独立になるので、平均への回帰だけ落として
      選手の真の水準は残せる。
  条件: 起点2日＋終盤2日で最低4日、共変量の1日を足して 日数>=5 が必要。
      現在 日数>=5 は 1,011行（>=4 の 1,408 から3割減）。
      サンプルが減るので今は実装しない。蓄積後に再検討する。

--- 再検定のスケジュール: 3ヶ月ごと・直近窓で回す ---------------------------
  12ヶ月ぶんを1人にプールしない。検定は「選手＝固定の切片」を仮定しているが、
  整備技能は年単位で動く（ペラ調整中心から整備に踏み込む、等の転機が実際にある）。
  技能がドリフトする場合、長期間を1人にプールすると異なる真値を平均することに
  なり、選手間分散が減衰して検出力が落ちる。
  下の感度表で σ_b=0.003 の「12ヶ月=94%」が最もドリフトに脆く、額面通りには
  受け取れない。

  運用:
    - 3ヶ月ごとに、直近3ヶ月窓のデータだけで再検定する
    - σ_b=0.007 なら3ヶ月で検出力99%。待つ理由がそもそも無い
    - 窓を跨いで結果が揺れる場合、それ自体がドリフトの証拠になる
    - 次回: 2026-10-31 を目安（本解析 2026-07-31 の3ヶ月後）

--- n=2 のままでは原理的に届かない ------------------------------------------
  §3 のとおり n=2 で検出力80%には選手 7,149 人が必要だが、稼働選手は
  約1,500人（実測15日で1,283人）。母数を増やす道は塞がっている。
  選手数ではなく「選手あたり行数」を時間で積む以外に到達手段は無い。

検出力の出し方:
  均衡計画（1選手あたり n 行）では、並べ替え検定の統計量（選手間分散）は
  F = MSB/MSW と単調同値。よって
      F_alt =d= c * F_null,   c = 1 + n * σ_b^2 / σ_w^2
  が成り立つ。null の F を1回サンプリングすれば、その95%点と c だけで
      検出力 = P(F_null > F95 / c)
  が出る。scipy 不要。

実行:
  py scripts/powerMotorMaintenance.py
"""

import json
import os
import random
import sys
from collections import Counter, defaultdict

BASE = r"C:\Users\USER\boatrace\localdata\motor_maintenance_base.json"
SIGMA_B = 0.007          # 仮定する選手間SD（秒）
N_ACTIVE_RACERS = 1500   # 稼働選手数の概算（実測 15日で 1,283人）
WINDOW_DAYS = 15         # motorParts の窓 20260715-20260729
REPORT = []


def say(*a):
    line = " ".join(str(x) for x in a)
    print(line)
    REPORT.append(line)


def head(t):
    say("\n" + "=" * 72)
    say(t)
    say("=" * 72)


def mean(xs):
    return sum(xs) / len(xs) if xs else None


def slope(xs, ys):
    mx, my = mean(xs), mean(ys)
    den = sum((x - mx) ** 2 for x in xs)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den


def between_var(groups):
    gm = [mean(v) for v in groups.values()]
    g = mean(gm)
    return mean([(x - g) ** 2 for x in gm])


def perm_test(groups, n_perm=10000, seed=20260731):
    obs = between_var(groups)
    pool = [v for vs in groups.values() for v in vs]
    sizes = [len(v) for v in groups.values()]
    rnd = random.Random(seed)
    null = []
    for _ in range(n_perm):
        rnd.shuffle(pool)
        i, g = 0, {}
        for j, s in enumerate(sizes):
            g[j] = pool[i:i + s]
            i += s
        null.append(between_var(g))
    null.sort()
    p = (sum(1 for x in null if x >= obs) + 1) / (len(null) + 1)
    return obs, null[len(null) // 2], p


def chi2(df, rnd):
    return rnd.gammavariate(df / 2.0, 2.0)


def null_F_sample(k, n, n_sim=20000, seed=1):
    """均衡計画 k群×n の帰無 F 分布を χ² 比で直接サンプリング。"""
    df1, df2 = k - 1, k * (n - 1)
    rnd = random.Random(seed)
    return sorted((chi2(df1, rnd) / df1) / (chi2(df2, rnd) / df2) for _ in range(n_sim))


def power_for(k, n, sig_b, sig_w, alpha=0.05, cache={}):
    if n < 2 or k < 2:
        return None
    key = (k, n)
    if key not in cache:
        cache[key] = null_F_sample(k, n)
    null = cache[key]
    crit = null[int(len(null) * (1 - alpha))]
    c = 1.0 + n * sig_b ** 2 / sig_w ** 2
    thr = crit / c
    return sum(1 for f in null if f > thr) / len(null)


def main():
    rows = json.load(open(BASE, encoding="utf-8"))["rows"]
    meas = [r for r in rows if r.get("短縮秒") is not None]

    # ---- 残差化（buildMotorMaintenance.py と同じ回帰） ----
    xs = [r["展示_序盤"] for r in meas]
    ys = [r["短縮秒"] for r in meas]
    b = slope(xs, ys)
    a = mean(ys) - b * mean(xs)

    resid = defaultdict(list)
    early = defaultdict(list)
    for r in meas:
        resid[r["登番"]].append(r["短縮秒"] - (a + b * r["展示_序盤"]))
        early[r["登番"]].append(r["展示_序盤"])
    rmulti = {k: v for k, v in resid.items() if len(v) >= 2}
    emulti = {k: v for k, v in early.items() if len(v) >= 2}

    head("§1 σ_within の逆算")
    ss = sum(sum((x - mean(v)) ** 2 for x in v) for v in rmulti.values())
    dof = sum(len(v) - 1 for v in rmulti.values())
    var_w = ss / dof
    sig_w = var_w ** 0.5
    say(f"  n>=2 の選手 {len(rmulti)} 人 / {sum(len(v) for v in rmulti.values())} 行")
    say(f"  プールした群内分散 σ_w^2 = {var_w:.6f}   σ_w = {sig_w:.4f} 秒")
    say(f"  仮定 σ_b = {SIGMA_B} 秒")
    icc = SIGMA_B ** 2 / (SIGMA_B ** 2 + var_w)
    say(f"  ICC = σ_b^2/(σ_b^2+σ_w^2) = {icc:.4f}")
    say(f"  → 短縮秒のばらつきのうち選手由来は {icc*100:.1f}%。残りは節ごとの当たり外れ。")

    say(f"\n  参考: 群サイズの分布 {dict(sorted(Counter(len(v) for v in rmulti.values()).items()))}")

    # F代理の妥当性チェック（実データは不均衡なので概算）
    head("§2 F代理の妥当性（実データで並べ替えと突き合わせ）")
    obs, med, p_perm = perm_test(rmulti)
    say(f"  並べ替え検定: 観測 {obs:.6f} / 帰無中央値 {med:.6f} / p = {p_perm:.4f}")
    k_eff = len(rmulti)
    n_eff = sum(len(v) for v in rmulti.values()) / k_eff
    say(f"  実データは不均衡（平均 n={n_eff:.2f}）。均衡近似 k={k_eff}, n=2 での")
    pw_now = power_for(k_eff, 2, SIGMA_B, sig_w)
    say(f"  現状の検出力（σ_b=0.007 が真だと仮定した場合）= {pw_now*100:.1f}%")
    say(f"  → 効果が実在しても {pw_now*100:.0f}% しか拾えない。p=0.25 は未決で当然。")

    # ---- 検出力グリッド ----
    head("§3 検出力80%に届く条件（σ_b=0.007, α=0.05）")
    say("  選手あたり行数 n × 選手数 k → 検出力 / 必要総行数")
    say(f"  {'n':>3} | " + " ".join(f"k={k:<5}" for k in (125, 250, 500, 1000, 1500)))
    for n in (2, 3, 4, 6, 8, 10, 15, 20):
        cells = []
        for k in (125, 250, 500, 1000, 1500):
            pw = power_for(k, n, SIGMA_B, sig_w)
            cells.append(f"{pw*100:5.1f}%")
        say(f"  {n:>3} | " + " ".join(cells))

    say("\n  各 n で検出力80%に必要な選手数と総行数:")
    for n in (2, 3, 4, 6, 8, 10, 15, 20):
        lo, hi = 2, 40000
        need = None
        while lo <= hi:
            mid = (lo + hi) // 2
            if power_for(mid, n, SIGMA_B, sig_w) >= 0.80:
                need = mid
                hi = mid - 1
            else:
                lo = mid + 1
        if need:
            say(f"    n={n:>2}: 選手 {need:>6,} 人 → 総行数 {need*n:>7,}")
        else:
            say(f"    n={n:>2}: 40,000人でも届かない")

    # ---- 時間換算 ----
    head("§4 いつ届くか（現在の産出ペースから換算）")
    rate_all = len(meas) / WINDOW_DAYS
    clean = [r for r in meas if not r["不完全節"]]
    rate_clean = len(clean) / WINDOW_DAYS
    say(f"  産出ペース: 日数>=4 の行 {len(meas):,} / {WINDOW_DAYS}日 = {rate_all:.1f} 行/日")
    say(f"              不完全節を除くと {len(clean):,} / {WINDOW_DAYS}日 = {rate_clean:.1f} 行/日")
    say(f"  稼働選手数の概算: {N_ACTIVE_RACERS:,} 人（実測 {WINDOW_DAYS}日で 1,283 人が出現）")
    say("\n  ※実運用は不均衡（よく走る選手ほど行が増える）。均衡計画は検出力を")
    say("    やや楽観する側に働くので、下表は最短側の見積り。")

    for label, rate in (("全行", rate_all), ("不完全節を除く", rate_clean)):
        say(f"\n  --- {label}（{rate:.1f} 行/日） ---")
        say(f"  {'経過':>6} | {'総行数':>8} | {'平均n':>6} | {'検出力':>7}")
        for months in (1, 2, 3, 4, 6, 9, 12, 18, 24):
            days = months * 30
            total = rate * days
            n_avg = total / N_ACTIVE_RACERS
            if n_avg < 2:
                say(f"  {months:>4}ヶ月 | {total:>8,.0f} | {n_avg:>6.2f} | {'n<2':>7}")
                continue
            pw = power_for(N_ACTIVE_RACERS, int(round(n_avg)), SIGMA_B, sig_w)
            say(f"  {months:>4}ヶ月 | {total:>8,.0f} | {n_avg:>6.2f} | {pw*100:>6.1f}%")

    # ---- 序盤そのものの個人差 ----
    head("§5 序盤そのものに選手差があるか（同じ並べ替え検定）")
    say("  対象: 展示_序盤（正規化済み・正=その日の平均より速い）")
    obs_e, med_e, p_e = perm_test(emulti)
    say(f"  n>=2 の {len(emulti)} 人 / {sum(len(v) for v in emulti.values())} 行")
    say(f"  観測 {obs_e:.6f} / 帰無中央値 {med_e:.6f} / 比 {obs_e/med_e:.3f}")
    say(f"  p = {p_e:.4f}")
    ss_e = sum(sum((x - mean(v)) ** 2 for x in v) for v in emulti.values())
    dof_e = sum(len(v) - 1 for v in emulti.values())
    vw_e = ss_e / dof_e
    excess = obs_e - med_e
    say(f"  群内分散 {vw_e:.6f} (σ_w={vw_e**0.5:.4f}秒) / 超過分 {excess:+.6f}")
    if excess > 0:
        say(f"  → 選手間SDに直すと約 {excess**0.5:.4f} 秒")

    out = os.path.join(os.path.dirname(BASE), "power_report.txt")
    open(out, "w", encoding="utf-8").write("\n".join(REPORT))
    say(f"\n  レポート: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
