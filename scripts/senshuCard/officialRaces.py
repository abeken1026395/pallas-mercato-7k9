"""選手カード：公式の数え方にそろえた艇ごとの表を作る。

results/*.json（公式レース結果）を土台に、
- 着7〜16の責任の有無（S0/S1、L0/L1、K0/K1）を Kファイル由来のコードで引く
- results に無いレース（不成立など）を Kファイルから足す
公式の出走＝着1〜15のうち責任外の失格（S0）・責任外の出遅れ（L0）・「00」を除き、責任のある欠場（K1）を加えたもの。

Kファイル由来のコード
- kdata/entriesFull.csv・kdata/racesAll.csv（2025-07-22〜2026-07-21・全行）
- data/senshuCard/kExtra.csv（それ以外の日。着が普通でない行と、results に無いレースの全行＝full=1）
"""
import csv
import glob
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CM = {'01': 1, '02': 2, '03': 3, '04': 4, '05': 5, '06': 6, 'F': 14, 'S0': 9, 'S1': 9, 'S2': 7,
      'L0': 15, 'L1': 15, 'K0': 16, 'K1': 16, '00': 13}


def rkey(d8, jcd, rno):
    return f"{d8}_{int(jcd):02d}_{int(rno)}"


def kst(s):
    """Kファイルの ST 表記（0.11 / F0.03 / L / 空）を数に。F は負の数、それ以外の読めないものは None"""
    s = (s or '').strip()
    if not s:
        return None
    if s.startswith('F'):
        try:
            return -float(s[1:])
        except ValueError:
            return None
    try:
        return float(s)
    except ValueError:
        return None


def load(last=None):
    """艇ごとの行（dict）のリストを返す。last（YYYYMMDD）より後の日は読まない"""
    rows = []
    have = set()
    for f in sorted(glob.glob(os.path.join(ROOT, 'results', '*.json'))):
        d = os.path.basename(f)[:8]
        if last and d > last:
            continue
        for r in json.load(open(f, encoding='utf-8'))['結果']:
            rk = rkey(d, r['場コード'], str(r['レース']).replace('R', ''))
            have.add(rk)
            for b in r['艇']:
                rows.append(dict(date=d, jo=f"{int(r['場コード']):02d}", rno=int(str(r['レース']).replace('R', '')), rk=rk,
                                 waku=b.get('枠'), toban=int(b['登番']), course=b.get('コース'), st=b.get('ST'),
                                 chaku=b.get('着'), kim=r.get('決まり手'), k=None, src='r', name=b.get('氏名')))
    # 責任の有無のコード
    code = {}
    kim = {}
    for r in csv.DictReader(open(os.path.join(ROOT, 'kdata', 'racesAll.csv'), encoding='utf-8')):
        kim[rkey('20' + r['hd'], r['jcd'], r['rno'])] = r['kimarite']
    add = []
    def take(r, kimarite):
        d8 = '20' + r['hd']
        if last and d8 > last:
            return
        rk = rkey(d8, r['jcd'], r['rno'])
        code.setdefault(f"{rk}_{int(r['toban'])}", r['chaku'])
        if rk not in have:
            ch = r['chaku']
            sh = (r.get('shinnyu') or '').strip()
            add.append(dict(date=d8, jo=f"{int(r['jcd']):02d}", rno=int(r['rno']), rk=rk, waku=int(r['waku']), toban=int(r['toban']),
                            course=int(sh) if sh and ch not in ('K0', 'K1') else None, st=kst(r.get('st')),
                            chaku=CM[ch], kim=kimarite, k=ch, src='k'))
    for r in csv.DictReader(open(os.path.join(ROOT, 'kdata', 'entriesFull.csv'), encoding='utf-8')):
        take(r, kim.get(rkey('20' + r['hd'], r['jcd'], r['rno'])))
    for r in csv.DictReader(open(os.path.join(ROOT, 'data', 'senshuCard', 'kExtra.csv'), encoding='utf-8')):
        d8 = '20' + r['hd']
        if last and d8 > last:
            continue
        rk = rkey(d8, r['jcd'], r['rno'])
        code.setdefault(f"{rk}_{int(r['toban'])}", r['chaku'])
        if r['full'] == '1' and rk not in have:
            take(r, r['kimarite'])
    seen = set()
    for a in add:
        kk = (a['rk'], a['toban'])
        if kk in seen:
            continue
        seen.add(kk)
        rows.append(a)
    for x in rows:
        if x['src'] == 'r':
            x['k'] = code.get(f"{x['rk']}_{x['toban']}")
        ch, k = x['chaku'], x['k']
        x['off'] = (isinstance(ch, int) and 1 <= ch <= 15 and k not in ('S0', 'L0', '00')) or k == 'K1'
    return rows


if __name__ == '__main__':
    rs = load('20261002')
    print(len(rs), sum(r['off'] for r in rs), sum(r['src'] == 'k' for r in rs))
