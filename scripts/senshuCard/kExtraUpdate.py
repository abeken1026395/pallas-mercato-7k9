"""選手カード：Kファイル（data/kfiles/kYYMMDD.lzh）から data/senshuCard/kExtra.csv に新しい日を足す。

PC の週1タスク（scripts/senshuCardKWeekly.ps1）から呼ぶ。mbrace は Actions から取れないため。
足す行（officialRaces.py が読む形）
- 着が 01〜06 でない行（S0/S1/S2・L0/L1・K0/K1・F・00）… full=0
- results/ に無いレースの全行 … full=1
足す日：kExtra.csv の最後の日より後、かつ results/YYYYMMDD.json がある日、かつ「今日の2日前」まで。
すでにある行は足さない。書くのは追記だけ（既存の行は変えない）。

使い方: python scripts/senshuCard/kExtraUpdate.py [今日 YYYYMMDD]
"""
import csv
import datetime as dt
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
OUT = os.path.join(ROOT, 'data', 'senshuCard', 'kExtra.csv')
COLS = ['hd', 'jcd', 'rno', 'chaku', 'waku', 'toban', 'shinnyu', 'st', 'kimarite', 'full']
NORMAL = {'01', '02', '03', '04', '05', '06'}
FIRST = '260722'   # kdata/entriesFull.csv の翌日


def haveRaces(d8):
    p = os.path.join(ROOT, 'results', d8 + '.json')
    if not os.path.exists(p):
        return None
    return {(int(r['場コード']), int(str(r['レース']).replace('R', ''))) for r in json.load(open(p, encoding='utf-8'))['結果']}


def rowsOf(entries, races, have):
    """entries・races：kparser の行。have：results にある (場, R) の集合"""
    kim = {(int(r['jcd']), int(r['rno'])): r.get('kimarite', '') for r in races}
    out = []
    for e in entries:
        key = (int(e['jcd']), int(e['rno']))
        full = key not in have
        if not full and e['chaku'] in NORMAL:
            continue
        out.append([e['hd'], f"{int(e['jcd']):02d}", str(int(e['rno'])), e['chaku'], e['waku'], e['toban'],
                    e.get('shinnyu', ''), e.get('st', ''), kim.get(key, ''), '1' if full else '0'])
    return out


def main():
    import buildMotorUsage as BM
    import kparser
    today = sys.argv[1] if len(sys.argv) > 1 else dt.date.today().strftime('%Y%m%d')
    t = dt.date(int(today[:4]), int(today[4:6]), int(today[6:]))
    lastOk = (t - dt.timedelta(2)).strftime('%y%m%d')
    old = list(csv.reader(open(OUT, encoding='utf-8')))
    assert old[0] == COLS, old[0]
    seen = {tuple(r) for r in old[1:]}
    maxHd = max(r[0] for r in old[1:])
    add, days, skip = [], [], []
    for f in sorted(glob.glob(os.path.join(ROOT, 'data', 'kfiles', 'k*.lzh'))):
        m = re.match(r'k(\d{6})\.lzh$', os.path.basename(f))
        if not m:
            continue
        hd = m.group(1)
        if hd <= maxHd or hd < FIRST or hd > lastOk:
            continue
        have = haveRaces('20' + hd)
        if have is None:
            skip.append(hd)
            continue
        res = kparser.parse_day(BM.decode_kfile(f), hd)
        rs = [r for r in rowsOf(res['entries'], res['races'], have) if tuple(r) not in seen]
        add += rs
        days.append((hd, len(rs)))
    print('足す日', days, '結果が無く見送った日', skip, '足す行', len(add))
    if add:
        with open(OUT, 'a', encoding='utf-8', newline='') as fo:
            w = csv.writer(fo, lineterminator='\r\n')   # 既存の kExtra.csv は CRLF
            for r in add:
                w.writerow(r)


if __name__ == '__main__':
    main()
