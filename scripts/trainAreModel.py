# -*- coding: utf-8 -*-
"""荒れモデル（scripts/areModel.py）の係数を引き直して data/areModel.json を書く。

  python scripts/trainAreModel.py [--kexport DIR] [--until YYYYMMDD] [--start YYYYMMDD] [--out PATH]

本番と同じ特徴量を作るため、data/racerFormIndex.json（buildRacerFormIndex.py）の集計を日ごとに再現する。
本番では、ある日 X の判定は前日 X-1 の 03:30 に作られた racerFormIndex を使う（X-2 までの結果）。
学習でも同じずれを再現し、X の特徴量には X-2 までの結果だけを使う。

--kexport は Kファイルから書き出した kExportEntries.csv.gz / kExportRaces.csv.gz のフォルダ（ローカル専用）。
results/ が始まる 2025-07-15 より前の履歴と学習データを補う。無ければ results/ だけで学習する。
級別は、results の 級別コード があればそれ、無ければ docs/data/rankHistory.json の当日の級別。

sklearn と numpy が要る（学習するときだけ。本番の build_highlights.py は要らない）。
"""
import argparse, csv, datetime, glob, gzip, json, os, sys
from bisect import bisect_right
from collections import deque, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import areModel  # noqa: E402

HARAN_TH = 5000
MIN_LAST, MIN_C, MIN_ST, MIN_VEN = 10, 5, 20, 200   # buildRacerFormIndex.py と同じ母数ガード
RESULTS_FROM = '20250715'
CODE2LV = {1: 'A1', 2: 'A2', 3: 'B1', 4: 'B2'}


def norm_chaku(v):
    """buildRacerFormIndex.norm_chaku と同じ。Kファイルの記号は results の着コードに読み替える。"""
    s = str(v).strip()
    if s.startswith('K') or s == '':
        return None
    if s[0] in 'FLS':
        return 6
    try:
        n = int(s)
    except ValueError:
        return None
    if 1 <= n <= 6:
        return n
    if 7 <= n <= 15:
        return 6
    return None


class Form:
    """racerFormIndex.json の racers / venues を日次で再現する。"""
    def __init__(self):
        self.last = {}; self.cc = {}; self.st = {}; self.ven = {}

    def add_race(self, jcd, boats, pay):
        b1 = next((b for b in boats if b['waku'] == 1), None)
        if b1 is not None:
            c = norm_chaku(b1['chaku'])
            if c is not None:
                v = self.ven.setdefault(jcd, [0, 0, 0, 0])
                v[0] += 1
                v[1] += c not in (1, 2, 3)
        if pay:
            v = self.ven.setdefault(jcd, [0, 0, 0, 0])
            v[2] += 1
            v[3] += pay >= HARAN_TH
        for b in boats:
            t = str(b['toban'])
            c = norm_chaku(b['chaku'])
            if c is not None:
                self.last.setdefault(t, deque(maxlen=20)).append(c)
                if b['course']:
                    self.cc.setdefault((t, str(b['course'])), deque(maxlen=10)).append(c)
            s = b['st']
            if s is not None:
                r = self.st.setdefault(t, [0, 0.0]); r[0] += 1; r[1] += s

    def racer(self, t):
        t = str(t)
        L = self.last.get(t) or []
        S = self.st.get(t) or [0, 0.0]
        cl = {}
        for k in '123456':
            C = self.cc.get((t, k)) or []
            if len(C) >= MIN_C:
                cl[k] = round(sum(C) / len(C), 3)
        return {'last20': round(sum(L) / len(L), 3) if len(L) >= MIN_LAST else None,
                'c1last10': cl.get('1'), 'cLast10': cl,
                'avgSt': round(S[1] / S[0], 4) if S[0] >= MIN_ST else None}

    def venue(self, j):
        v = self.ven.get(j) or [0, 0, 0, 0]
        return {'out1Rate': round(v[1] / v[0] * 100, 2) if v[0] >= MIN_VEN else None,
                'areRate': round(v[3] / v[2] * 100, 2) if v[2] >= MIN_VEN else None}


class Racers(dict):
    def __init__(self, form): super().__init__(); self.f = form
    def get(self, k, d=None): return self.f.racer(k)


class Venues(dict):
    def __init__(self, form): super().__init__(); self.f = form
    def get(self, k, d=None): return self.f.venue(k)


def load_days(kexport, until):
    days = defaultdict(list)   # hd -> [(jcd, rno, boats, pay)]
    if kexport:
        ent = defaultdict(list)
        with gzip.open(os.path.join(kexport, 'kExportEntries.csv.gz'), 'rt', encoding='utf-8') as fp:
            for r in csv.DictReader(fp):
                if r['hd'] >= RESULTS_FROM:
                    continue
                st = r['st']
                try:
                    stv = float(st) if st and st[0] in '0.' else None
                except ValueError:
                    stv = None
                ent[(r['hd'], r['jcd'], int(r['rno']))].append(
                    {'waku': int(r['waku']), 'toban': int(r['toban']), 'chaku': r['chaku'], 'st': stv,
                     'course': int(r['shinnyu']) if r['shinnyu'] else None, 'lvcode': None})
        with gzip.open(os.path.join(kexport, 'kExportRaces.csv.gz'), 'rt', encoding='utf-8') as fp:
            for r in csv.DictReader(fp):
                if r['hd'] >= RESULTS_FROM:
                    continue
                k = (r['hd'], r['jcd'], int(r['rno']))
                try:
                    pay = int(r['pay3t'].replace(',', ''))
                except ValueError:
                    pay = None
                days[r['hd']].append((k[1], k[2], sorted(ent.get(k, []), key=lambda b: b['waku']), pay))
    for f in sorted(glob.glob(os.path.join('results', '20*.json'))):
        d = os.path.basename(f)[:8]
        if d < RESULTS_FROM or d > until:
            continue
        for x in json.load(open(f, encoding='utf-8')).get('結果', []) or []:
            bo = [{'waku': b['枠'], 'toban': int(b['登番']), 'chaku': b.get('着'), 'st': b.get('ST'),
                   'course': b.get('コース'), 'lvcode': b.get('級別コード')}
                  for b in sorted(x.get('艇', []) or [], key=lambda b: b['枠'])]
            days[d].append((str(x['場コード']).zfill(2), int(str(x['レース']).rstrip('R')), bo, x.get('三連単配当')))
    return days


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--kexport')
    ap.add_argument('--start', default='20240701')
    ap.add_argument('--until', default=datetime.date.today().strftime('%Y%m%d'))
    ap.add_argument('--out', default=os.path.join('data', 'areModel.json'))
    ap.add_argument('--start-date', dest='kado', default=None, help='稼働日 YYYYMMDD')
    ap.add_argument('--dump', help='学習行の特徴量と点数を書き出す（検証用）')
    a = ap.parse_args()
    import numpy as np
    from sklearn.linear_model import LogisticRegression

    rh = json.load(open(os.path.join('docs', 'data', 'rankHistory.json'), encoding='utf-8'))['選手']
    rh = {t: (sorted(r)) for t, r in rh.items()}
    rhd = {t: [x[0] for x in r] for t, r in rh.items()}

    def lv_of(b, d):
        if b['lvcode']:
            return CODE2LV.get(b['lvcode'], 'B1')
        t = str(b['toban']); rec = rh.get(t)
        if not rec:
            return 'B1'
        i = bisect_right(rhd[t], '%s-%s-%s' % (d[:4], d[4:6], d[6:]))
        return rec[i - 1][1] if i else 'B1'

    days = load_days(a.kexport, a.until)
    form = Form(); R = Racers(form); V = Venues(form)
    order = sorted(days)
    applied = 0
    rows = []
    for d in order:
        dd = datetime.datetime.strptime(d, '%Y%m%d').date()
        cut = (dd - datetime.timedelta(days=2)).strftime('%Y%m%d')
        while applied < len(order) and order[applied] <= cut:
            for (jcd, rno, bo, pay) in days[order[applied]]:
                form.add_race(jcd, bo, pay)
            applied += 1
        if d < a.start:
            continue
        for (jcd, rno, bo, pay) in days[d]:
            if len(bo) != 6 or not pay:
                continue
            f = areModel.features([lv_of(b, d) for b in bo], [b['toban'] for b in bo], R, V, jcd, rno)
            rows.append((d, jcd, rno, int(pay >= HARAN_TH), [f[k] for k in areModel.FEATURES]))
    F = areModel.FEATURES
    X = np.array([[np.nan if v is None else v for v in r[4]] for r in rows], float)
    y = np.array([r[3] for r in rows])
    imp = np.nanmean(X, 0)
    Xf = np.where(np.isnan(X), imp, X)
    mu, sd = Xf.mean(0), Xf.std(0) + 1e-9
    m = LogisticRegression(C=1.0, max_iter=5000).fit((Xf - mu) / sd, y)
    p = m.predict_proba((Xf - mu) / sd)[:, 1]
    dates = np.array([r[0] for r in rows])
    recent = p[dates >= (datetime.datetime.strptime(a.until, '%Y%m%d') - datetime.timedelta(days=182)).strftime('%Y%m%d')]
    th_h = float(np.quantile(recent, 0.80)); th_k = float(np.quantile(recent, 0.422))
    out = {
        '版': 'are20v1',
        '目的変数': '3連単の払戻が5,000円以上か（HARAN_TH）',
        '学習期間': {'開始': rows[0][0], '終了': rows[-1][0], 'レース数': len(rows)},
        '特徴の時点': '判定する日の2日前までの結果（本番の racerFormIndex.json と同じずれ）',
        '閾値の決め方': '学習期間の直近182日の点数分布で、上位20%を波乱、下位42.2%を堅め',
        '稼働日': a.kado,
        '特徴': F,
        '係数': [round(float(c), 6) for c in m.coef_[0]],
        '切片': round(float(m.intercept_[0]), 6),
        '埋め値': [round(float(v), 6) for v in imp],
        '平均': [round(float(v), 6) for v in mu],
        '標準偏差': [round(float(v), 6) for v in sd],
        '閾値': {'波乱': round(th_h, 6), '堅め': round(th_k, 6)},
        'note': '順位付けと分類の線引きにだけ使う。読者に確率として出さない。',
    }
    with open(a.out, 'w', encoding='utf-8') as fp:
        json.dump(out, fp, ensure_ascii=False, indent=1)
    print('rows', len(rows), 'base', round(float(y.mean()), 4), 'th', out['閾値'])
    if a.dump:
        np.savez_compressed(a.dump, X=X, y=y, d=dates, jcd=np.array([r[1] for r in rows]),
                            rno=np.array([r[2] for r in rows]))


if __name__ == '__main__':
    main()
