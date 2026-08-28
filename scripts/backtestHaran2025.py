#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""haranModel morning7 の係数を 2025年後半に当てて、係数の期間安定性を見る（A-2）。

これは walk-forward ではない。
係数は 2026-01〜2026-08 の results から引いたもので、それを時系列的に前の
2025年後半へ当てている。学習に 2025年後半は入っていないのでリークではないが、
未来のデータで作った係数を過去に当てているだけなので **性能の証明にはならない**。
ここから言えるのは「係数の方向と大きさが期間をまたいで保たれているか」まで。

読むだけ:
  data/haranModel.json       … 係数・欠損代替値・平均・標準偏差（手打ちしない）
  results/YYYYMMDD.json      … 着・ST・コース・登番
  docs/data/rankHistory.json … 級別の履歴
書くのは /tmp/ 配下だけ。リポジトリには何も残さない。

特徴量は「朝の生成時点」を再現するため、各レースの履歴を **前日まで** で打ち切る。
同じ日の先行レースは履歴に入れない。
"""

import csv
import json
import os
import sys
import time
from bisect import bisect_right
from collections import defaultdict
from datetime import date, timedelta

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = '/tmp'

WARMUP_FROM = date(2025, 7, 15)   # 助走：履歴の積み上げのみ。評価に含めない
EVAL_FROM = date(2025, 10, 1)     # 評価対象
EVAL_TO = date(2025, 12, 31)

# 母数ガード。data/racerFormIndex.json の「母数ガード」の実測値と同じ値。
#   {"last20": 10, "c1last10": 5, "avgSt": 20, "out1Rate": 200}
# racerFormIndex.json 自体は 2026年時点の集計済みインデックスで
# 2025年の「前日まで」を再現できないため、ここでは値だけを借りて履歴を自前で積む。
MIN_LAST20 = 10
MIN_C1LAST10 = 5
MIN_AVGST = 20
MIN_VENOUT = 200

# 級別→数値。scripts/build_highlights.py の LV と同じ。
LV = {'A1': 4, 'A2': 3, 'B1': 2, 'B2': 1}
# 外3艇の級別合計だけは「級別不明でも欠損にせず 2 として加算」する。
# build_highlights.py の sum(LV.get(b.get('級別'), 2) for b in bo[3:]) と同一。
LV_OUT_DEFAULT = 2

FEATURE_ORDER = ['rk1', 'last20', 'rkout', 'venOut', 'c1last10', 'avgSt', 'midLastBest']
NEGATIVE_KEYS = {'rk1', 'midLastBest'}


# ---------------------------------------------------------------- モデル読み込み

def load_model(path):
    with open(path, encoding='utf-8') as fp:
        d = json.load(fp)
    m = d['モデル']['morning7']
    feats = []
    for f in m['特徴量']:
        feats.append({
            'key': f['キー'],
            'co': float(f['係数']),
            'med': float(f['欠損代替値']),
            'mu': float(f['平均']),
            'sd': float(f['標準偏差']),
        })
    keys = [f['key'] for f in feats]

    # 検算1：特徴キーが7個で、順序も想定どおりであること
    assert len(keys) == 7, '特徴量が7個でない: %d個 %s' % (len(keys), keys)
    assert keys == FEATURE_ORDER, '特徴キーの順序が想定と違う: %s' % (keys,)

    # 検算2：係数の符号が rk1 と midLastBest のみ負、他5つが正であること
    for f in feats:
        if f['key'] in NEGATIVE_KEYS:
            assert f['co'] < 0, '%s の係数が負でない: %s' % (f['key'], f['co'])
        else:
            assert f['co'] > 0, '%s の係数が正でない: %s' % (f['key'], f['co'])
    assert sum(1 for f in feats if f['co'] < 0) == 2, '負の係数が2個でない'

    assert m['切片'] is None, '切片が null でない: %s' % (m['切片'],)
    return d, feats, m


# ---------------------------------------------------------------- 級別履歴

class RankHistory:
    """登番 → [(日付, 級別), ...]。当該レース日 **以前** の最後のエントリを採用する。

    docs/data/rankHistory.json の注記のとおり、日付は改定日ではなく
    「改定後にその選手が初めて出走した日」。1件も無ければ級別不明（None）。
    """

    def __init__(self, path):
        with open(path, encoding='utf-8') as fp:
            d = json.load(fp)
        self.tbl = {}
        for toban, rows in d['選手'].items():
            srt = sorted((str(r[0]), str(r[1])) for r in rows)
            self.tbl[str(toban)] = ([r[0] for r in srt], [r[1] for r in srt])

    def rank_on(self, toban, iso):
        rec = self.tbl.get(str(toban))
        if not rec:
            return None
        days, ranks = rec
        i = bisect_right(days, iso)
        if i == 0:
            return None
        return ranks[i - 1]


# ---------------------------------------------------------------- 着とST

def round_chaku(x):
    """着の丸め。7〜15 は 6 に丸める。16（欠場）は None（分母から除く）。"""
    try:
        v = int(x)
    except (TypeError, ValueError):
        return None
    if v == 16:
        return None
    if 7 <= v <= 15:
        return 6
    if 1 <= v <= 6:
        return v
    return None


def num_st(x):
    """ST は数値のもののみ採用。欠損・非数値は除外。"""
    if x is None or isinstance(x, bool):
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- 履歴の器

class Hist:
    def __init__(self):
        self.chaku = defaultdict(list)     # 登番 → 丸め後の着（全走・時系列）
        self.c1 = defaultdict(list)        # 登番 → コース1で走ったときの着
        self.st_sum = defaultdict(float)   # 登番 → ST合計
        self.st_n = defaultdict(int)       # 登番 → ST本数
        self.ven_n = defaultdict(int)      # 場コード → 枠1の着が確定したレース数
        self.ven_out = defaultdict(int)    # 場コード → 枠1が4着以下だったレース数

    def last20(self, toban):
        a = self.chaku.get(toban)
        if not a or len(a) < MIN_LAST20:
            return None
        w = a[-20:]
        return sum(w) / len(w)

    def c1last10(self, toban):
        a = self.c1.get(toban)
        if not a or len(a) < MIN_C1LAST10:
            return None
        w = a[-10:]
        return sum(w) / len(w)

    def avg_st(self, toban):
        n = self.st_n.get(toban, 0)
        if n < MIN_AVGST:
            return None
        return self.st_sum[toban] / n

    def ven_out_rate(self, ba):
        n = self.ven_n.get(ba, 0)
        if n < MIN_VENOUT:
            return None
        return self.ven_out[ba] / n * 100.0


# ---------------------------------------------------------------- 特徴量

def build_features(race, hist, rh, iso):
    """1レースぶんの生の特徴量を返す。値が取れないものは None（＝欠損）。"""
    boats = {int(b['枠']): b for b in (race.get('艇') or []) if b.get('枠') is not None}
    b1 = boats.get(1)
    if b1 is None:
        return None
    t1 = str(b1.get('登番'))

    rk1 = LV.get(rh.rank_on(t1, iso))   # 級別不明なら None（欠損）

    # 外3艇：級別不明の艇は 2 として加算する（欠損にしない）
    rkout = 0
    for w in (4, 5, 6):
        b = boats.get(w)
        if b is None:
            rkout += LV_OUT_DEFAULT
            continue
        rkout += LV.get(rh.rank_on(str(b.get('登番')), iso), LV_OUT_DEFAULT)

    mids = []
    for w in (2, 3):
        b = boats.get(w)
        if b is None:
            continue
        v = hist.last20(str(b.get('登番')))
        if v is not None:
            mids.append(v)

    return {
        'rk1': rk1,
        'last20': hist.last20(t1),
        'rkout': float(rkout),
        'venOut': hist.ven_out_rate(race.get('場コード')),
        'c1last10': hist.c1last10(t1),
        'avgSt': hist.avg_st(t1),
        'midLastBest': (min(mids) if mids else None),
    }


def score_of(vals, feats):
    """スコア = Σ 係数 ×（値 − 平均）÷ 標準偏差。欠損は欠損代替値で埋めてから標準化。切片なし。"""
    z = 0.0
    for f in feats:
        v = vals.get(f['key'])
        if v is None:
            v = f['med']
        z += f['co'] * ((float(v) - f['mu']) / f['sd'])
    return z


# ---------------------------------------------------------------- 履歴の更新

def apply_day(races, hist):
    """その日のレースを履歴に足す。評価が終わったあとに呼ぶ（当日を含めないため）。"""
    for race in races:
        boats = race.get('艇') or []
        for b in boats:
            toban = str(b.get('登番'))
            c = round_chaku(b.get('着'))
            if c is not None:
                hist.chaku[toban].append(c)
                if b.get('コース') == 1:
                    hist.c1[toban].append(c)
            st = num_st(b.get('ST'))
            if st is not None:
                hist.st_sum[toban] += st
                hist.st_n[toban] += 1
        # 場の①着外率：枠1の着が確定したレースだけを分母に入れる。
        # 枠1が欠場（着=16）のレースは「4着以下だったか」を判定できないため分母から除く。
        b1 = next((b for b in boats if b.get('枠') == 1), None)
        if b1 is not None:
            c1 = round_chaku(b1.get('着'))
            if c1 is not None:
                ba = race.get('場コード')
                hist.ven_n[ba] += 1
                if c1 >= 4:
                    hist.ven_out[ba] += 1


# ---------------------------------------------------------------- 指標

def auc_of(scores, labels):
    """順位ベースの AUC（同値は平均順位）。片方のクラスが無ければ None。"""
    pairs = sorted(zip(scores, labels))
    n = len(pairs)
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and pairs[j + 1][0] == pairs[i][0]:
            j += 1
        r = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[k] = r
        i = j + 1
    npos = sum(l for _, l in pairs)
    nneg = n - npos
    if npos == 0 or nneg == 0:
        return None
    s = sum(r for r, (_, l) in zip(ranks, pairs) if l == 1)
    return (s - npos * (npos + 1) / 2.0) / (npos * nneg)


def decile(rows, top=True, frac=0.10):
    """スコア上位（下位）frac の①着外率(%)・母数・場コード集合を返す。

    件数は round(N*frac)。スコアは連続値なので同値の境界は事実上起きない。
    """
    if not rows:
        return None, 0, set()
    k = max(1, int(round(len(rows) * frac)))
    sel = sorted(rows, key=lambda r: r['score'], reverse=top)[:k]
    rate = sum(r['y'] for r in sel) / len(sel) * 100.0
    return rate, len(sel), set(r['ba'] for r in sel)


# ---------------------------------------------------------------- 本体

def main():
    t0 = time.time()
    os.makedirs(OUTDIR, exist_ok=True)

    raw, feats, model = load_model(os.path.join(REPO, 'data', 'haranModel.json'))
    rh = RankHistory(os.path.join(REPO, 'docs', 'data', 'rankHistory.json'))

    hist = Hist()
    rows = []
    n_days = 0
    n_days_eval = 0
    n_seen = 0          # 評価期間に走査したレース総数
    n_no_waku1 = 0      # 枠1が存在しないレース（除外）
    n_chaku16 = 0       # 枠1の着が16のレース（除外）
    missing_files = []

    d = WARMUP_FROM
    while d <= EVAL_TO:
        iso = d.isoformat()
        path = os.path.join(REPO, 'results', d.strftime('%Y%m%d') + '.json')
        if not os.path.exists(path):
            missing_files.append(iso)
            d += timedelta(days=1)
            continue
        with open(path, encoding='utf-8') as fp:
            day = json.load(fp)
        races = day.get('結果') or []
        n_days += 1

        if d >= EVAL_FROM:
            n_days_eval += 1
            for race in races:
                n_seen += 1
                boats = race.get('艇') or []
                b1 = next((b for b in boats if b.get('枠') == 1), None)
                if b1 is None:
                    n_no_waku1 += 1
                    continue
                y1 = round_chaku(b1.get('着'))
                if y1 is None:
                    # 着=16（欠場）ほか、着が確定していないレースは母集団から除く
                    n_chaku16 += 1
                    continue
                vals = build_features(race, hist, rh, iso)
                rows.append({
                    'date': iso,
                    'month': iso[:7],
                    'ba': race.get('場コード'),
                    'race': race.get('レース'),
                    'toban1': b1.get('登番'),
                    'score': score_of(vals, feats),
                    'y': 1 if y1 >= 4 else 0,
                    'chaku1': b1.get('着'),
                    'vals': vals,
                })

        apply_day(races, hist)
        d += timedelta(days=1)

    # ------------------------------------------------------------ 集計
    out = []

    def p(s=''):
        out.append(s)
        print(s)

    p('=' * 78)
    p('haranModel morning7 の係数を 2025年後半に当てた結果（A-2 期間安定性）')
    p('=' * 78)
    p('※ walk-forward ではない。2026年のデータで引いた係数を 2025年後半に当てている。')
    p('※ これは性能の証明にはならない。')
    p()
    p('モデル: data/haranModel.json  updated=%s' % raw['updated'])
    p('係数の学習期間: %s' % model['学習期間'])
    p('検算1 特徴キー7個・順序 = %s  → OK' % ' / '.join(FEATURE_ORDER))
    p('検算2 係数の符号: %s' % ', '.join('%s=%+g' % (f['key'], f['co']) for f in feats))
    p('       負は rk1 と midLastBest の2つのみ、他5つは正  → OK')
    p()
    p('--- 1. 走査した日数・評価レース数・除外レース数 ---')
    p('助走 %s〜%s（履歴の積み上げのみ）' % (WARMUP_FROM, EVAL_FROM - timedelta(days=1)))
    p('評価 %s〜%s' % (EVAL_FROM, EVAL_TO))
    p('走査した日数（助走＋評価）: %d 日' % n_days)
    p('  うち評価対象の日数      : %d 日' % n_days_eval)
    p('  results が無い日        : %d 日 %s' % (len(missing_files), missing_files[:10]))
    p('評価期間のレース総数        : %d' % n_seen)
    p('  除外（枠1が存在しない）  : %d' % n_no_waku1)
    p('  除外（枠1の着が16/未確定）: %d' % n_chaku16)
    p('評価レース数（母集団）      : %d' % len(rows))

    scores = [r['score'] for r in rows]
    labels = [r['y'] for r in rows]
    auc = auc_of(scores, labels)
    base = sum(labels) / len(labels) * 100.0

    p()
    p('--- 2. AUC ---')
    p('AUC: %.4f' % auc)

    top_rate, top_n, top_ba = decile(rows, top=True)
    bot_rate, bot_n, _ = decile(rows, top=False)
    p()
    p('--- 3. 上位10% / 下位10% の①着外率 ---')
    p('上位10%%の①着外率: %.1f%%  (n=%d)' % (top_rate, top_n))
    p('下位10%%の①着外率: %.1f%%  (n=%d)' % (bot_rate, bot_n))

    p()
    p('--- 4. 上位10%が散る場数 ---')
    p('%d 場  （母集団に出てくる場数 %d）' % (len(top_ba), len(set(r['ba'] for r in rows))))

    p()
    p('--- 5. 月ごとのAUCと上位10%①着外率 ---')
    months = sorted(set(r['month'] for r in rows))
    m_auc = []
    m_top = []
    p('%-9s%7s%9s%10s%10s%9s' % ('月', 'n', 'AUC', '上位10%', '下位10%', '母集団'))
    for m in months:
        sub = [r for r in rows if r['month'] == m]
        a = auc_of([r['score'] for r in sub], [r['y'] for r in sub])
        t, _tn, _tb = decile(sub, top=True)
        b, _bn, _bb = decile(sub, top=False)
        bs = sum(r['y'] for r in sub) / len(sub) * 100.0
        m_auc.append(a)
        m_top.append(t)
        p('%-9s%7d%9.4f%9.1f%%%9.1f%%%8.1f%%' % (m, len(sub), a, t, b, bs))
    p('AUC 最小〜最大            : %.4f 〜 %.4f' % (min(m_auc), max(m_auc)))
    p('上位10%%①着外率 最小〜最大 : %.1f%% 〜 %.1f%%' % (min(m_top), max(m_top)))

    p()
    p('--- 6. 母集団の①着外率（2025年後半の実測）---')
    p('%.1f%%  (%d / %d)' % (base, sum(labels), len(labels)))

    p()
    p('--- 7. 特徴ごとの欠損率（月別・7特徴すべて）---')
    p('※ 欠損＝生の値が取れず欠損代替値で埋めた割合。rkout は定義上けっして欠損しない。')
    p('%-9s%7s' % ('月', 'n') + ''.join('%13s' % k for k in FEATURE_ORDER))
    miss_rows = []
    for m in months + ['全期間']:
        sub = rows if m == '全期間' else [r for r in rows if r['month'] == m]
        cells = []
        rec = {'月': m, 'n': len(sub)}
        for k in FEATURE_ORDER:
            c = sum(1 for r in sub if r['vals'][k] is None)
            rate = c / len(sub) * 100.0
            cells.append('%12.1f%%' % rate)
            rec[k] = round(rate, 2)
        miss_rows.append(rec)
        p('%-9s%7d' % (m, len(sub)) + ''.join(cells))

    p()
    p('--- 8. 2026年実測との差 ---')
    ev = model['評価指標']
    p('%-22s%12s%12s%12s' % ('指標', '2026実測', '2025後半', '差'))
    p('%-24s%12.4f%12.4f%+12.4f' % ('AUC', ev['AUC'], auc, auc - ev['AUC']))
    p('%-20s%12.1f%12.1f%+12.1f' % ('上位10%①着外率(%)', ev['上位10%の①着外率'],
                                    top_rate, top_rate - ev['上位10%の①着外率']))
    p('%-20s%12.1f%12.1f%+12.1f' % ('下位10%①着外率(%)', ev['下位10%の①着外率'],
                                    bot_rate, bot_rate - ev['下位10%の①着外率']))
    p('%-20s%12d%12d%+12d' % ('上位10%が散る場数', ev['上位10%が散る場数'],
                              len(top_ba), len(top_ba) - ev['上位10%が散る場数']))
    p('%-21s%12.1f%12.1f%+12.1f' % ('母集団①着外率(%)', ev['母集団の①着外率'],
                                    base, base - ev['母集団の①着外率']))
    p('※ 2026実測の値も data/haranModel.json の 評価指標 から読んでいる（手打ちしない）。')

    # ------------------------------------------------------------ CSV 出力（/tmp のみ）
    races_csv = os.path.join(OUTDIR, 'haran2025_races.csv')
    with open(races_csv, 'w', encoding='utf-8', newline='') as fp:
        w = csv.writer(fp)
        w.writerow(['date', 'ba', 'race', 'toban1', 'chaku1', 'y', 'score'] + FEATURE_ORDER)
        for r in rows:
            w.writerow([r['date'], r['ba'], r['race'], r['toban1'], r['chaku1'], r['y'],
                        '%.6f' % r['score']] +
                       ['' if r['vals'][k] is None else '%.6f' % float(r['vals'][k])
                        for k in FEATURE_ORDER])

    miss_csv = os.path.join(OUTDIR, 'haran2025_missing.csv')
    with open(miss_csv, 'w', encoding='utf-8', newline='') as fp:
        w = csv.DictWriter(fp, fieldnames=['月', 'n'] + FEATURE_ORDER)
        w.writeheader()
        for rec in miss_rows:
            w.writerow(rec)

    report_txt = os.path.join(OUTDIR, 'haran2025_report.txt')
    with open(report_txt, 'w', encoding='utf-8') as fp:
        fp.write('\n'.join(out) + '\n')

    print()
    print('出力: %s / %s / %s' % (races_csv, miss_csv, report_txt))
    print('実行時間: %.1f 秒' % (time.time() - t0))
    return 0


if __name__ == '__main__':
    sys.exit(main())
