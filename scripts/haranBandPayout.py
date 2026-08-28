#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""波乱指数（haranModel morning7 の z）の十分位ごとに、実際に出た配当の分布を数える（A-3）。

★これは回収率ではない。
  うちは確定オッズを持っていない。odds/ は締切前スナップショット1点で、
  確定払戻と20%以上ずれる例が実測で 172レース中4件（2.3%）ある。
  よってここでは odds/ を一切参照せず、results の確定払戻（三連単配当）を
  「どの帯にどんな配当が出ているか」として数えるだけにする。
  回収率・期待値・妙味の判定は出さない。買い目も出さない。

読むだけ:
  data/haranModel.json       … 係数・欠損代替値・平均・標準偏差（手打ちしない）
  results/YYYYMMDD.json      … 着・ST・コース・登番・三連単配当・決まり手
  docs/data/rankHistory.json … 級別の履歴（読み取りのみ。docs/ には書かない）
書くのは /tmp/ 配下だけ。リポジトリには何も残さない。

特徴量は「朝の生成時点」を再現するため、各レースの履歴を **前日まで** で打ち切る。
同じ日の先行レースは履歴に入れない。scripts/backtestHaran2025.py と同じ作りで、
級別の引き方も同じ（2025年分の results に級別が無いため rankHistory で統一する）。
"""

import csv
import hashlib
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
EVAL_FROM = date(2025, 10, 1)     # 評価対象（母数ガードの助走2.5ヶ月ぶんを空ける）
EVAL_TO = date(2026, 8, 22)       # これ以降は当日分が未確定のことがあるため含めない

NBAND = 10                        # 十分位
PAYOUT_TH = (5000, 10000)         # 3連単配当のしきい値（円）

# 母数ガード。scripts/backtestHaran2025.py と同じ値（data/racerFormIndex.json 由来）。
MIN_LAST20 = 10
MIN_C1LAST10 = 5
MIN_AVGST = 20
MIN_VENOUT = 200

# 級別→数値。scripts/build_highlights.py の LV と同じ。
LV = {'A1': 4, 'A2': 3, 'B1': 2, 'B2': 1}
# 外3艇の級別合計だけは「級別不明でも欠損にせず 2 として加算」する。
LV_OUT_DEFAULT = 2

FEATURE_ORDER = ['rk1', 'last20', 'rkout', 'venOut', 'c1last10', 'avgSt', 'midLastBest']
NEGATIVE_KEYS = {'rk1', 'midLastBest'}

KIMARITE = ['逃げ', '差し', 'まくり', 'まくり差し', '抜き', '恵まれ']


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
    """登番 → [(日付, 級別), ...]。当該レース日 **以前** の最後のエントリを採用する。"""

    def __init__(self, path):
        with open(path, encoding='utf-8') as fp:
            d = json.load(fp)
        self.meta = {k: v for k, v in d.items() if k != '選手'}
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
    if x is None or isinstance(x, bool):
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- 履歴の器

class Hist:
    def __init__(self):
        self.chaku = defaultdict(list)
        self.c1 = defaultdict(list)
        self.st_sum = defaultdict(float)
        self.st_n = defaultdict(int)
        self.ven_n = defaultdict(int)
        self.ven_out = defaultdict(int)

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


# ---------------------------------------------------------------- 特徴量とスコア

def build_features(race, hist, rh, iso):
    boats = {int(b['枠']): b for b in (race.get('艇') or []) if b.get('枠') is not None}
    b1 = boats.get(1)
    if b1 is None:
        return None
    t1 = str(b1.get('登番'))

    rk1 = LV.get(rh.rank_on(t1, iso))

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
    """z = Σ 係数 ×（値 − 平均）÷ 標準偏差。欠損は欠損代替値で埋めてから標準化。切片なし。"""
    z = 0.0
    for f in feats:
        v = vals.get(f['key'])
        if v is None:
            v = f['med']
        z += f['co'] * ((float(v) - f['mu']) / f['sd'])
    return z


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
        b1 = next((b for b in boats if b.get('枠') == 1), None)
        if b1 is not None:
            c1 = round_chaku(b1.get('着'))
            if c1 is not None:
                ba = race.get('場コード')
                hist.ven_n[ba] += 1
                if c1 >= 4:
                    hist.ven_out[ba] += 1


# ---------------------------------------------------------------- 集計の道具

def median(xs):
    if not xs:
        return None
    s = sorted(xs)
    n = len(s)
    return float(s[n // 2]) if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def pct(a, b):
    return (a / b * 100.0) if b else float('nan')


def split_bands(rows, nband):
    """z の昇順で、件数がほぼ等しい nband 個の帯に切る。帯1 = z 最小、帯10 = z 最大。

    余りは前の帯から1件ずつ配る。z は連続値なので同値の境界は事実上起きない。
    """
    srt = sorted(rows, key=lambda r: r['z'])
    n = len(srt)
    base, rem = divmod(n, nband)
    bands = []
    i = 0
    for k in range(nband):
        size = base + (1 if k < rem else 0)
        bands.append(srt[i:i + size])
        i += size
    assert i == n
    return bands


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fp:
        for chunk in iter(lambda: fp.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------- 本体

def main():
    t0 = time.time()
    os.makedirs(OUTDIR, exist_ok=True)

    raw, feats, model = load_model(os.path.join(REPO, 'data', 'haranModel.json'))
    rh = RankHistory(os.path.join(REPO, 'docs', 'data', 'rankHistory.json'))

    hist = Hist()
    rows = []
    n_days = n_days_eval = 0
    n_seen = 0
    n_no_waku1 = 0      # 枠1が存在しないレース（除外）
    n_chaku16 = 0       # 枠1の着が16/未確定のレース（除外）
    n_no_pay = 0        # 三連単配当が取れないレース（除外）
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
                    n_chaku16 += 1
                    continue
                try:
                    pay = int(race.get('三連単配当'))
                except (TypeError, ValueError):
                    pay = 0
                if pay <= 0:
                    n_no_pay += 1
                    continue
                win = next((b.get('枠') for b in boats if b.get('着') == 1), None)
                assert win is None or win == race.get('1着'), \
                    '1着の枠が着順と食い違う: %s %s' % (iso, race.get('レース'))
                vals = build_features(race, hist, rh, iso)
                rows.append({
                    'date': iso,
                    'month': iso[:7],
                    'ba': race.get('場コード'),
                    'race': race.get('レース'),
                    'z': score_of(vals, feats),
                    'chaku1': y1,
                    'win1': 1 if y1 == 1 else 0,
                    'out1': 1 if y1 >= 4 else 0,
                    'pay': pay,
                    'kimarite': race.get('決まり手') or '不明',
                    'winWaku': win,
                })

        apply_day(races, hist)
        d += timedelta(days=1)

    bands = split_bands(rows, NBAND)

    # ------------------------------------------------------------ 出力
    out = []

    def p(s=''):
        out.append(s)
        print(s)

    p('=' * 96)
    p('波乱指数（morning7 の z）の十分位ごとの配当分布（A-3）')
    p('=' * 96)
    p('★これは回収率ではない。確定オッズを持っていないため回収率・期待値は算出しない。')
    p('★odds/ は一切参照していない。配当は results/ の確定払戻（三連単配当）のみ。')
    p('★「どの帯にどんな配当が出ているか」を数えただけで、買える／買えないの判断は含まない。')
    p()
    p('モデル : data/haranModel.json  updated=%s  morning7（7特徴・切片なし）' % raw['updated'])
    p('係数の学習期間 : %s' % model['学習期間'])
    p('級別 : docs/data/rankHistory.json（%s / 生成 %s）を全期間で使用。'
      % (rh.meta.get('期間'), rh.meta.get('生成')))
    p('       2025年分の results に級別が無いため、年をまたいで引き方を統一した。')
    p('検算1 特徴キー7個・順序 = %s  → OK' % ' / '.join(FEATURE_ORDER))
    p('検算2 係数の符号: %s' % ', '.join('%s=%+g' % (f['key'], f['co']) for f in feats))
    p('       負は rk1 と midLastBest の2つのみ、他5つは正  → OK')
    p()
    p('--- 1. 走査した日数・レース数・除外数 ---')
    p('助走 %s〜%s（履歴の積み上げのみ・評価に含めない）'
      % (WARMUP_FROM, EVAL_FROM - timedelta(days=1)))
    p('評価 %s〜%s' % (EVAL_FROM, EVAL_TO))
    p('走査した日数（助走＋評価）  : %d 日' % n_days)
    p('  うち評価対象の日数        : %d 日' % n_days_eval)
    p('  results が無い日          : %d 日 %s' % (len(missing_files), missing_files[:10]))
    p('評価期間のレース総数        : %d' % n_seen)
    p('  除外（枠1が存在しない）    : %d' % n_no_waku1)
    p('  除外（枠1の着が16/未確定）  : %d' % n_chaku16)
    p('  除外（三連単配当が無い）    : %d' % n_no_pay)
    p('評価レース数（母集団）      : %d' % len(rows))

    base_win = pct(sum(r['win1'] for r in rows), len(rows))
    base_out = pct(sum(r['out1'] for r in rows), len(rows))
    base_med = median([r['pay'] for r in rows])
    p()
    p('--- 2. 母集団（全帯まとめ）---')
    p('①1着率 %.1f%% / ①着外率 %.1f%% / 3連単配当の中央値 %s円 / 5000円以上 %.1f%% / 10000円以上 %.1f%%'
      % (base_win, base_out, ('%d' % base_med),
         pct(sum(1 for r in rows if r['pay'] >= PAYOUT_TH[0]), len(rows)),
         pct(sum(1 for r in rows if r['pay'] >= PAYOUT_TH[1]), len(rows))))
    p('（参考）data/haranModel.json の 母集団の①着外率 = %.1f%%'
      % model['評価指標']['母集団の①着外率'])

    p()
    p('--- 3. 十分位ごとの表（帯1 = z 最小＝堅い / 帯10 = z 最大＝波乱寄り）---')
    p('%-5s%8s%11s%11s%11s%11s%11s%11s%11s'
      % ('帯', 'n', 'zの下限', 'zの上限', '①1着率', '①着外率', '配当中央値', '5000円↑', '10000円↑'))
    band_rows = []
    for i, bd in enumerate(bands, 1):
        n = len(bd)
        pays = [r['pay'] for r in bd]
        rec = {
            'band': i,
            'n': n,
            'zmin': bd[0]['z'],
            'zmax': bd[-1]['z'],
            'win1': pct(sum(r['win1'] for r in bd), n),
            'out1': pct(sum(r['out1'] for r in bd), n),
            'payMedian': median(pays),
            'pay5000': pct(sum(1 for v in pays if v >= PAYOUT_TH[0]), n),
            'pay10000': pct(sum(1 for v in pays if v >= PAYOUT_TH[1]), n),
        }
        band_rows.append(rec)
        p('%-5d%8d%11.3f%11.3f%10.1f%%%10.1f%%%11d%10.1f%%%10.1f%%'
          % (i, n, rec['zmin'], rec['zmax'], rec['win1'], rec['out1'],
             rec['payMedian'], rec['pay5000'], rec['pay10000']))
    p('%-5s%8d%11s%11s%10.1f%%%10.1f%%%11d%10.1f%%%10.1f%%'
      % ('全体', len(rows), '', '', base_win, base_out, base_med,
         pct(sum(1 for r in rows if r['pay'] >= PAYOUT_TH[0]), len(rows)),
         pct(sum(1 for r in rows if r['pay'] >= PAYOUT_TH[1]), len(rows))))

    p()
    p('--- 4. 決まり手の分布（帯ごと・%）---')
    kcols = KIMARITE + ['不明']
    p('%-5s%8s' % ('帯', 'n') + ''.join('%11s' % k for k in kcols))
    kim_rows = []
    for i, bd in enumerate(bands, 1):
        n = len(bd)
        c = defaultdict(int)
        for r in bd:
            c[r['kimarite'] if r['kimarite'] in KIMARITE else '不明'] += 1
        kim_rows.append(dict({'band': i, 'n': n}, **{k: round(pct(c[k], n), 2) for k in kcols}))
        p('%-5d%8d' % (i, n) + ''.join('%10.1f%%' % pct(c[k], n) for k in kcols))
    c = defaultdict(int)
    for r in rows:
        c[r['kimarite'] if r['kimarite'] in KIMARITE else '不明'] += 1
    p('%-5s%8d' % ('全体', len(rows)) + ''.join('%10.1f%%' % pct(c[k], len(rows)) for k in kcols))

    p()
    p('--- 5. 1着艇の艇番分布（帯ごと・%）---')
    p('%-5s%8s' % ('帯', 'n') + ''.join('%11s' % ('%d号艇' % w) for w in range(1, 7)))
    win_rows = []
    for i, bd in enumerate(bands, 1):
        n = len(bd)
        c = defaultdict(int)
        for r in bd:
            c[r['winWaku']] += 1
        win_rows.append(dict({'band': i, 'n': n}, **{str(w): round(pct(c[w], n), 2)
                                                     for w in range(1, 7)}))
        p('%-5d%8d' % (i, n) + ''.join('%10.1f%%' % pct(c[w], n) for w in range(1, 7)))
    c = defaultdict(int)
    for r in rows:
        c[r['winWaku']] += 1
    p('%-5s%8d' % ('全体', len(rows)) + ''.join('%10.1f%%' % pct(c[w], len(rows))
                                                for w in range(1, 7)))

    p()
    p('--- 6. 配当の分位（帯ごと・円）---')
    p('※ 中央値だけだと帯の中の散らばりが見えないため、参考に四分位も出す。')
    p('%-5s%8s%11s%11s%11s%11s' % ('帯', 'n', '25%点', '中央値', '75%点', '90%点'))
    for i, bd in enumerate(bands, 1):
        pays = sorted(r['pay'] for r in bd)
        n = len(pays)
        q = lambda f: pays[min(n - 1, int(n * f))]
        p('%-5d%8d%11d%11d%11d%11d' % (i, n, q(0.25), median(pays), q(0.75), q(0.90)))

    p()
    p('★再掲：上の配当はすべて確定払戻の実測であって、回収率ではない。')
    p('★odds/ の締切前スナップショットは使っていないため、「買えたか」は一切分からない。')

    # ------------------------------------------------------------ /tmp への書き出し
    races_csv = os.path.join(OUTDIR, 'haranBandPayout_races.csv')
    with open(races_csv, 'w', encoding='utf-8', newline='') as fp:
        w = csv.writer(fp)
        w.writerow(['date', 'ba', 'race', 'z', 'chaku1', 'winWaku', 'kimarite', 'pay'])
        for r in sorted(rows, key=lambda r: r['z']):
            w.writerow([r['date'], r['ba'], r['race'], '%.6f' % r['z'], r['chaku1'],
                        r['winWaku'], r['kimarite'], r['pay']])

    band_json = os.path.join(OUTDIR, 'haranBandPayout_bands.json')
    with open(band_json, 'w', encoding='utf-8') as fp:
        json.dump({
            '注意': 'これは回収率ではない。確定払戻の分布を数えただけ。odds/ は未参照。',
            '評価期間': [EVAL_FROM.isoformat(), EVAL_TO.isoformat()],
            'レース数': len(rows),
            '帯': band_rows,
            '決まり手': kim_rows,
            '1着艇番': win_rows,
        }, fp, ensure_ascii=False, indent=1)

    report_txt = os.path.join(OUTDIR, 'haranBandPayout_report.txt')
    with open(report_txt, 'w', encoding='utf-8') as fp:
        fp.write('\n'.join(out) + '\n')

    me = os.path.abspath(__file__)
    print()
    print('出力: %s / %s / %s' % (races_csv, band_json, report_txt))
    print('スクリプト: %s  %d bytes  sha256=%s' % (me, os.path.getsize(me), sha256_of(me)))
    print('実行時間: %.1f 秒' % (time.time() - t0))
    return 0


if __name__ == '__main__':
    sys.exit(main())
