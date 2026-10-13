"""翌日（CSVにある最も新しい開催日）の出走表が、番組どおりそろったかを判定する。

そろった = 終了コード0 ／ まだ = 終了コード1（標準出力に不足を書く）
判定は buildRaceRoom.build の「未完成」判定と同じ（番組にあるのに出走表にない場・締切12本そろわない場）。
番組表（gradeSchedule）の当該日が読めないときは、そろったとは言わない（入力欠損を完了と取り違えない）。
"""
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import buildRaceRoom as b  # noqa: E402


def check(csv_path=b.CSV_PATH, grade_path=b.GRADE_PATH):
    rows = list(csv.DictReader(open(csv_path, encoding='utf-8-sig')))
    dates = sorted({r['開催日'] for r in rows if r.get('開催日', '').isdigit()})
    if not dates:
        return False, '出走表に開催日がない'
    date = dates[-1]
    try:
        days = json.load(open(grade_path, encoding='utf-8')).get('days', {})
    except (OSError, ValueError):
        return False, date + ' 番組表が読めない'
    grade_day = days.get(date, {})
    if not grade_day:
        return False, date + ' 番組表に当該日がない'
    _, warn = b.build(date, rows, grade_day)
    if warn:
        return False, date + ' 未完成: ' + ' / '.join(warn)
    return True, date + ' そろった（番組表 %d 場）' % len(grade_day)


if __name__ == '__main__':
    ok, msg = check(*sys.argv[1:3])
    print(('COMPLETE ' if ok else 'INCOMPLETE ') + msg)
    sys.exit(0 if ok else 1)
