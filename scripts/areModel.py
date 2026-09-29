# -*- coding: utf-8 -*-
"""朝の分類（波乱／混戦／堅め）を決める「荒れモデル」。

学習（scripts/trainAreModel.py）と本番（scripts/build_highlights.py）が同じ関数で特徴量を作るための共有部品。
目的変数は「3連単の払戻が 5,000円以上か」（HARAN_TH と同じ線）。
点数は 0〜1 の値になるが、並び替えと分類の線引きにだけ使う。読者に確率として出さない（サイト哲学）。

特徴量は朝の時点で手に入るものだけ：
  出走表の級別（6艇）・レース番号
  data/racerFormIndex.json の選手の直近20走平均着・コース別の直近10走平均着・過去平均ST
  data/racerFormIndex.json の場の①着外率・荒れ率
係数・標準化・欠損の埋め値・分類の線は data/areModel.json（手打ちしない）。
"""
import json
import math
import os

LV = {'A1': 4, 'A2': 3, 'B1': 2, 'B2': 1}

FEATURES = ['rk1', 'last20', 'rkout', 'venOut', 'c1last10', 'avgSt', 'midLastBest', 'venAre', 'lvSum26',
            'nA26', 'nB2', 'best26', 'sd26', 'sd16', 'rank1', 'gap23', 'race'] + \
           ['l20_%d' % i for i in range(2, 7)] + ['c10_%d' % i for i in range(2, 7)] + \
           ['lv_%d' % i for i in range(2, 7)]


def _std(a):
    m = sum(a) / len(a)
    return math.sqrt(sum((x - m) ** 2 for x in a) / len(a))


def features(lv, tob, racers, venues, jcd, rno):
    """lv: 6艇の級別（'A1' 等）。tob: 6艇の登番。racers/venues: racerFormIndex の racers/venues。
    枠順（1号艇から6号艇）で渡す。値が無い特徴は None（埋め値はモデル側）。"""
    lvn = [LV.get((x or '').strip(), 2) for x in lv]
    l20, c10 = [], []
    for w in range(6):
        r = racers.get(str(tob[w]).strip()) or {}
        l20.append(r.get('last20'))
        c10.append((r.get('cLast10') or {}).get(str(w + 1)))
    r1 = racers.get(str(tob[0]).strip()) or {}
    v = venues.get(str(jcd).zfill(2)) or {}
    others = [a for a in l20[1:] if a is not None]
    have = [a for a in l20 if a is not None]
    f = {
        'rk1': lvn[0], 'last20': l20[0], 'rkout': sum(lvn[3:]),
        'venOut': v.get('out1Rate'), 'c1last10': r1.get('c1last10'), 'avgSt': r1.get('avgSt'),
        'midLastBest': min([a for a in l20[1:3] if a is not None], default=None),
        'venAre': v.get('areRate'), 'lvSum26': sum(lvn[1:]),
        'nA26': sum(1 for a in lvn[1:] if a >= 3), 'nB2': sum(1 for a in lvn[1:] if a == 1),
        'best26': min(others) if others else None,
        'sd26': _std(others) if len(others) >= 3 else None,
        'sd16': _std(have) if len(have) >= 4 else None,
        'rank1': (sorted(have).index(l20[0]) if l20[0] is not None else None),
        'gap23': (sorted(others)[1] - sorted(others)[0] if len(others) >= 2 else None),
        'race': int(str(rno).rstrip('R')),
    }
    for i in range(1, 6):
        f['l20_%d' % (i + 1)] = l20[i]
        f['c10_%d' % (i + 1)] = c10[i]
        f['lv_%d' % (i + 1)] = lvn[i]
    return f


def load(path=os.path.join('data', 'areModel.json')):
    try:
        with open(path, encoding='utf-8') as fp:
            m = json.load(fp)
        if m.get('特徴') != FEATURES:
            return None
        return m
    except Exception:
        return None


def score(f, m):
    z = m['切片']
    for k, co, imp, mu, sd in zip(m['特徴'], m['係数'], m['埋め値'], m['平均'], m['標準偏差']):
        x = f.get(k)
        if x is None:
            x = imp
        z += co * ((float(x) - mu) / sd)
    return 1.0 / (1.0 + math.exp(-z))


def verdict(p, m):
    if p >= m['閾値']['波乱']:
        return '波乱'
    if p <= m['閾値']['堅め']:
        return '堅め'
    return '混戦'
