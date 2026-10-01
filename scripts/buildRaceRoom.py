"""オープンチャット「総合レース部屋」の告知文を出走表から生成する。

入力 : docs/racers/racers_today.csv（公式出走表）・docs/data/gradeSchedule.json（区分）
出力 : raceRoom/<開催日>.txt（CSVにある開催日ごと）・raceRoom/latest.txt（最も新しい開催日）
       docs/ の外に置くので Pages は起動しない。

- CSVにない場は載せない（推測で補わない）
- 公式の番組（gradeSchedule）にあるのにCSVにない場、締切が12本そろわない場があれば、
  先頭に「⚠未完成」の行を付ける（貼る前に気づけるように）
"""
import csv
import collections
import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(ROOT, 'docs', 'racers', 'racers_today.csv')
GRADE_PATH = os.path.join(ROOT, 'docs', 'data', 'gradeSchedule.json')
OUT_DIR = os.path.join(ROOT, 'raceRoom')

WEEK = '月火水木金土日'
VENUE = dict(zip(
    ['%02d' % i for i in range(1, 25)],
    ['桐生', '戸田', '江戸川', '平和島', '多摩川', '浜名湖', '蒲郡', '常滑', '津', '三国', 'びわこ', '住之江',
     '尼崎', '鳴門', '丸亀', '児島', '宮島', '徳山', '下関', '若松', '芦屋', '福岡', '唐津', '大村']))
SECTIONS = [
    ('モーニング', lambda h: h < 10),
    ('デイ', lambda h: 10 <= h < 14),
    ('ナイター', lambda h: 14 <= h < 17),
    ('ミッドナイト', lambda h: h >= 17),
]

GUIDE = """↓下の吹き出しマークから、今日のレースの話へ🚤

あなたの予想、ここに置いていきませんか？
「{example}12R 1-2-全」みたいに一言だけでOK。
根拠なし、勘だけ、本命1点だけ、全部歓迎です。

当たったら自慢、外したら供養。
人の予想に「乗った」「逆張りする」だけの返信もどうぞ。

🌙このスレッドは24時間OK（メインの0時〜7時ルールの対象外）
🔰はじめての方は、メインで特典を受け取って自己紹介してからどうぞ"""


def tag(info, day):
    ku = info.get('区分', '一般')
    grade = ku if ku in ('SG', 'G1', 'G2', 'G3') else ''
    fem = '女子' if ku in ('ヴィーナスシリーズ', 'オールレディース') or info.get('レディース') else ''
    end = '終' if day == '最終日' else ('初' if day == '初日' else '')
    if grade in ('SG', 'G1') and end == '終':
        return grade + end
    for t in (grade, fem, end):
        if t:
            return t
    return ''


def build(date, rows, grade_day):
    times = collections.defaultdict(set)
    nb, code = {}, {}
    for r in rows:
        if r['開催日'] != date:
            continue
        v = r['場名']
        if ':' in r['締切時刻']:
            times[v].add(r['締切時刻'])
        nb[v] = r['日目']
        code[v] = r['場コード'].zfill(2)

    venues = []
    for v in code:
        ts = sorted(times[v])
        if not ts:
            continue
        venues.append((ts[0], v, ts[-1], len(ts)))
    venues.sort()

    warn = []
    short = [v for _, v, _, n in venues if n < 12]
    if short:
        warn.append('締切が12本そろわない場：' + '・'.join(short))
    missing = sorted(set(grade_day) - set(code.values()))
    if missing:
        warn.append('番組にあるのに出走表にない場：' + '・'.join(VENUE.get(c, c) for c in missing))

    w = max(len(v) for _, v, _, _ in venues)
    d = datetime.date(int(date[:4]), int(date[4:6]), int(date[6:]))
    lines = []
    if warn:
        lines.append('⚠未完成（貼らない）：' + ' ／ '.join(warn))
        lines.append('')
    lines.append(f'🌅{d.month}/{d.day}({WEEK[d.weekday()]})総合レース部屋🌅')
    night_last = None
    for name, f in SECTIONS:
        group = [x for x in venues if f(int(x[0][:2]))]
        if not group:
            continue
        lines.append('')
        lines.append('【' + name + '】')
        for s, v, e, _ in group:
            t = tag(grade_day.get(code[v], {}), nb[v])
            lines.append(v + '　' * (w - len(v)) + '　' + s + '〜' + e + ('　' + t if t else ''))
        if name == 'ナイター':
            night_last = group[-1][1]

    # 見本の場：SG/G1/G2の場 → ナイターの最後の場 → 最後に締め切る場
    big = [v for _, v, _, _ in venues
           if grade_day.get(code[v], {}).get('区分') in ('SG', 'G1', 'G2')]
    example = big[0] if big else (night_last or max(venues, key=lambda x: x[2])[1])

    lines.append('')
    lines.append(GUIDE.format(example=example))
    return '\n'.join(lines) + '\n', warn


def main():
    rows = list(csv.DictReader(open(CSV_PATH, encoding='utf-8-sig')))
    try:
        days = json.load(open(GRADE_PATH, encoding='utf-8')).get('days', {})
    except (OSError, ValueError):
        days = {}
    dates = sorted({r['開催日'] for r in rows if r.get('開催日', '').isdigit()})
    if not dates:
        print('出走表に開催日がない。何も書かない')
        return 0
    os.makedirs(OUT_DIR, exist_ok=True)
    for date in dates:
        text, warn = build(date, rows, days.get(date, {}))
        with open(os.path.join(OUT_DIR, date + '.txt'), 'w', encoding='utf-8', newline='\n') as fp:
            fp.write(text)
        print(date, '未完成' if warn else '完成', ' / '.join(warn))
    latest = dates[-1]
    with open(os.path.join(OUT_DIR, latest + '.txt'), encoding='utf-8') as src, \
            open(os.path.join(OUT_DIR, 'latest.txt'), 'w', encoding='utf-8', newline='\n') as dst:
        dst.write(src.read())
    print('latest =', latest)
    return 0


if __name__ == '__main__':
    sys.exit(main())
