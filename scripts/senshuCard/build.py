"""選手カードのデータを一式作る（集計・優勝戦・技・積み上げた事実・直接対決）。

使い方:
  python3 scripts/senshuCard/fetchPrograms.py 20170101 最終日 番組フォルダ 20250714   # 番組を取る（すでにある日は取らない）
  python3 scripts/senshuCard/build.py 最終日 番組フォルダ 出力フォルダ

出力フォルダ
  card.json   … 選手ごとの集計・技（tg）・優勝（yc）。実験場 senshuCardE.html の card2D.json と同じ形
  ayumi.json  … 積み上げた事実
  h2h/0〜63.json・meta.json … 直接対決
  card/common.json・index.json・p/0〜63.json … ページ用に選手ごとに分けたもの（card.json と ayumi.json の中身）
最後に検査を走らせ、1つでも外れたら書き出さずに止まる（check.py）。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import buildCard as BC  # noqa: E402
import check  # noqa: E402
import facts  # noqa: E402
import h2h  # noqa: E402
import waza  # noqa: E402


def split(out, ay, d):
    """ページ用に分ける：common.json（窓・技の一覧・優勝の範囲）、index.json（登番→名前。検索用）、p/登番%64.json（選手ごと。ay＝積み上げた事実）"""
    os.makedirs(os.path.join(d, 'p'), exist_ok=True)
    json.dump({k: v for k, v in out.items() if k != 'players'}, open(os.path.join(d, 'common.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
    json.dump({t: P['name'] for t, P in out['players'].items()}, open(os.path.join(d, 'index.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
    shards = {}
    for t, P in out['players'].items():
        shards.setdefault(int(t) % 64, {})[t] = dict(P, ay=ay.get(t, {}))
    for k in range(64):
        json.dump(shards.get(k, {}), open(os.path.join(d, 'p', f'{k}.json'), 'w'), ensure_ascii=False, separators=(',', ':'))


def main():
    last, rawDir, outDir = sys.argv[1], sys.argv[2], sys.argv[3]
    out, rows = BC.build(last, rawDir)
    unk = sum(1 for x in rows if isinstance(x['chaku'], int) and 7 <= x['chaku'] <= 16 and x['src'] == 'r' and x['k'] is None)
    print('責任の有無が分からない行（Kファイルが無い日の着7〜16）', unk)
    wins = {W: (w['from'], w['to']) for W, w in out['win'].items()}
    pri = waza.build(BC.ROOT, rows, wins, out['players'], last)
    for W in pri:
        out['win'][W]['tagPrior'] = pri[W]
    out['tags'] = waza.TAGS
    ay = facts.build(BC.ROOT, rows, wins, out['players'])
    problems = check.run(out, ay)
    if problems:
        print('検査で止めた：')
        for p in problems:
            print(' -', p)
        sys.exit(1)
    os.makedirs(outDir, exist_ok=True)
    json.dump(out, open(os.path.join(outDir, 'card.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
    json.dump(ay, open(os.path.join(outDir, 'ayumi.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
    h2h.build(rows, set(out['players']), out['win']['all']['from'], last, os.path.join(outDir, 'h2h'))
    split(out, ay, os.path.join(outDir, 'card'))
    print('OK', last, '選手', len(out['players']))


if __name__ == '__main__':
    main()
