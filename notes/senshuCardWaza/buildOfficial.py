"""公式の出走の数え方にそろえた艇ごとの表（boatsOff.pkl）を作る（2026-10-04）。

公式の出走：責任外の失格（S0）・責任外の出遅れ（L0）・責任外の欠場（K0）と「00」は数えず、
責任のある欠場（K1）は数える。results/ に無いレース（不成立など）は Kファイルから足す。
これで出走数・レース数が card2.json と3期間とも全選手一致する（2026-10-04 実測）。

入力
- boats.pkl … load.py が results/ から作る表
- kdata/entriesFull.csv・kdata/racesAll.csv … Kファイル（2025-07-22〜2026-07-21）
- kSmall.csv … Drive codeShikyu\\kfileParse20261003\\kSmall.csv（kdata に無い日の、着が普通でない行と、results に無いレースの全行＝full=1）
"""
import csv
import pandas as pd

W = '/tmp/claude-0/-home-claude/94cc7118-f7b4-5f44-94a8-f2c262b6ac1a/scratchpad/'   # 作業場（使うときに書き換える）
R = '/home/claude/abeken1026395/pallas-mercato-7k9/'
CM = {'01': 1, '02': 2, '03': 3, '04': 4, '05': 5, '06': 6, 'F': 14, 'S0': 9, 'S1': 9, 'S2': 7,
      'L0': 15, 'L1': 15, 'K0': 16, 'K1': 16, '00': 13}


def key(hd, j, rn, tb=None):
    k = f"{hd}_{int(j):02d}_{int(rn)}"
    return k if tb is None else f"{k}_{int(tb)}"


df = pd.read_pickle(W + 'waza/boats.pkl')
df['key'] = df.date.str[2:] + '_' + df.jo + '_' + df.race.str.replace('R', '').astype(int).astype(str) + '_' + df.toban.astype(str)

# 着のコード（責任の有無）：results の着7〜16は責任の有無を区別しないので Kファイルから引く
code = {}
for r in csv.DictReader(open(R + 'kdata/entriesFull.csv', encoding='utf-8')):
    code[key(r['hd'], r['jcd'], r['rno'], r['toban'])] = r['chaku']
small = list(csv.DictReader(open(W + 'kSmall.csv', encoding='utf-8')))
for r in small:
    code.setdefault(key(r['hd'], r['jcd'], r['rno'], r['toban']), r['chaku'])
df['k'] = df.key.map(code)

# results に無いレースを Kファイルから足す
have = set(df.date.str[2:] + '_' + df.jo + '_' + df.race.str.replace('R', '').astype(int).astype(str))
kim = {key(r['hd'], r['jcd'], r['rno']): r['kimarite'] for r in csv.DictReader(open(R + 'kdata/racesAll.csv', encoding='utf-8'))}
add = []


def push(hd, j, rn, ch, wk, tb, sh, km):
    add.append(dict(date='20' + hd, jo=f'{int(j):02d}', race=f'{int(rn)}R', waku=int(wk), toban=int(tb),
                    course=float(sh) if sh.strip() and ch not in ('K0', 'K1') else None, st=None,
                    chaku=CM[ch], kim=km, k=ch))


for r in csv.DictReader(open(R + 'kdata/entriesFull.csv', encoding='utf-8')):
    if key(r['hd'], r['jcd'], r['rno']) not in have:
        push(r['hd'], r['jcd'], r['rno'], r['chaku'], r['waku'], r['toban'], r['shinnyu'], kim.get(key(r['hd'], r['jcd'], r['rno'])))
for r in small:
    if r['full'] == '1':
        push(r['hd'], r['jcd'], r['rno'], r['chaku'], r['waku'], r['toban'], r['shinnyu'], r['kimarite'])
A = pd.DataFrame(add).drop_duplicates(['date', 'jo', 'race', 'toban'])
full = pd.concat([df, A], ignore_index=True)
full['off'] = (full.chaku.between(1, 15) & ~full.k.isin(['S0', 'L0', '00'])) | (full.k == 'K1')
full.to_pickle(W + 'waza/boatsOff.pkl')
print(len(full), int(full.off.sum()))
