#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_highlights.py
出走表CSV＋モーターCSVを読み、本日の見どころ・展開文を計算して highlights.json に出力する。
ロジックは tenkai_logic.json の方針に準拠（買い目・確率・勝者断定・内心推測は出さない）。
使い方:
  python build_highlights.py [racers_csv] [motors_csv] [out_json]
  省略時: docs/racers/racers_today.csv  docs/motor/motors_all.csv  docs/highlights/highlights.json
"""
import csv, json, sys, os, datetime
from collections import defaultdict

import birthdayMark   # 誕生日マークの判定（scripts/birthdayMark.py）

RACERS = sys.argv[1] if len(sys.argv) > 1 else "docs/racers/racers_today.csv"
MOTORS = sys.argv[2] if len(sys.argv) > 2 else "docs/motor/motors_all.csv"
MOTOR_REPLACE = "docs/data/motorReplace.json"   # モーター新替の記録（手入力可・自動追記）
MOTOR_MIN_RUNS = 10                       # これ未満の走破数は機力を評価しない
OUT    = sys.argv[3] if len(sys.argv) > 3 else "docs/highlights/highlights.json"
KIM    = sys.argv[4] if len(sys.argv) > 4 else "docs/players/racerKimarite.csv"
WEATHER = sys.argv[5] if len(sys.argv) > 5 else "docs/data/weather.json"

# --- 翌日プレビュー・モード（HL_MODE=next）---
# 前夜に「明日」タブ用の highlights_next.json を生成する専用モード。
# 当日モード(HL_MODE未設定)の挙動・出力先・predictions書き込みには一切干渉しない。
# 出力先は OUT と同ディレクトリの highlights_next.json 固定（当日 highlights.json は触らない）。
NEXT = os.environ.get('HL_MODE') == 'next'
NEXT_OUT = os.path.join(os.path.dirname(OUT) or '.', 'highlights_next.json')

# --- 見どころが参照する選手成績JSON（期首固定項目のみ）---
# 見どころ index.html には全1,643名分の const PROF={...} が静的埋め込みされている。
# その正本は docs/data/racerStats.json（第1段で切り出し済み）。ここでは見どころが実際に
# 描画しうる選手だけに絞った軽量版を書き出し、index.html 側の PROF を将来この外部JSONへ
# 差し替えられるようにする。
# 出力キー名は「見どころ側の名前」に合わせる（ht/wt/fuku/w1/w2）。index.html の
# bProfHTML を書き換えずに読み替えられるようにするため。
RACER_STATS = "docs/data/racerStats.json"
STATS_OUT = os.path.join(os.path.dirname(OUT) or '.', 'racerStatsToday.json')

# 登録番号 -> 誕生日（和暦文字列）。誕生日マークの判定にだけ使う。
# racerStats.json が読めなければ空になり、マークが出ないだけで処理は止まらない。
BIRTH_MAP = birthdayMark.load_birth_map(RACER_STATS)

# 収録対象は「当日」だけでは足りない。見どころには 当日/明日/前日/前々日 の4タブがあり、
# いずれも同じ bProfHTML で選手情報を描画する。当日分だけに絞ると前日・前々日タブで
# 最大305名が「図鑑データが見つかりません」になるため、4ファイルの和集合を収録する。
# ファイル名は racerStatsToday.json のまま変えない（参照側の指示と整合させるため）。
STATS_SOURCES = ('highlights.json', 'highlights_next.json',
                 'highlights_prev.json', 'highlights_prev2.json')

# (見どころ側のキー名, racerStats.json 側のキー名)。bProfHTML が実際に読む16項目のみ。
# 出走表CSV由来の項目（全国勝率・当地勝率・枠・さされ率など）は由来が混ざるため入れない。
PROF_KEYS = (
    ('rank', 'rank'), ('branch', 'branch'), ('home', 'home'), ('age', 'age'),
    ('ht', 'height'), ('wt', 'weight'), ('blood', 'blood'), ('avgst', 'avgst'),
    ('syutsu', 'syutsu'), ('w1', 'win1'), ('w2', 'win2'), ('yusyo', 'yusyo'),
    ('f', 'f'), ('out', 'out'), ('fuku', 'fukusho'), ('c1', 'c1'),
)
FULL_RACES = 12  # 通常番組=12R。これ未満は「一部レースのみ（深夜に追加）」の暫定表示にする。

INTOP = {'大村':63,'徳山':62,'芦屋':64,'尼崎':62,'下関':60,'常滑':58,'住之江':55,'丸亀':56,
         '児島':55,'唐津':56,'若松':55,'宮島':54,'浜名湖':54,'三国':53,'蒲郡':54,'福岡':52,
         '鳴門':52,'びわこ':51,'多摩川':54,'平和島':50,'戸田':49,'津':54,'桐生':53,'江戸川':48}
CONFIRMED = {'尼崎','徳山','芦屋','下関','大村','常滑'}
MAKURI = {'戸田','江戸川','びわこ','平和島'}
K = '①②③④⑤⑥'

# --- 場特性の1行目（24場・断定しない範囲で水面の傾向のみ）---
# in天国(it>=58)/狭水面まくり場(MAKURI)/差し場を軸に、記者の1行目を作る。
NARROW = {'戸田','平和島','江戸川'}          # 狭い・インが残りにくい
SASHI  = {'常滑','蒲郡','児島','鳴門','丸亀'}  # うねり・差しが効きやすい傾向
# 〔着眼点の第1層〕場ごとに「まず何の数字を出すか」を決める。
#   根拠は docs/data/collapsePattern.json の実測（過去1年・①着外率と決まり手内訳）。
#   ①着外率の四分位 17.0 / 18.6 / 21.5 を目安に3群へ。
#   ラベルは材料名。人名は使わない（読者に出さないため、コード上も置かない）。
VENUE_FOCUS = {
    # 荒れ（①着外率20%超）＝崩れ方の実数を主材料に
    '戸田': 'collapseFirst', '平和島': 'collapseFirst', '桐生': 'collapseFirst',
    '多摩川': 'collapseFirst', '浜名湖': 'collapseFirst', 'びわこ': 'collapseFirst',
    '江戸川': 'collapseFirst', '三国': 'collapseFirst', '鳴門': 'collapseFirst',
    # 中間（①着外率 17〜20%台）＝当地勝率と平均STを主材料に
    '常滑': 'gapFirst', '宮島': 'gapFirst', '丸亀': 'gapFirst', '津': 'gapFirst',
    '児島': 'gapFirst', '唐津': 'gapFirst', '住之江': 'gapFirst', '蒲郡': 'gapFirst',
    # 堅い（①着外率 17%未満）＝モーターを主材料に
    '福岡': 'motorFirst', '芦屋': 'motorFirst', '若松': 'motorFirst', '尼崎': 'motorFirst',
    '大村': 'motorFirst', '徳山': 'motorFirst', '下関': 'motorFirst',
}
def ba_line(ba, it):
    if ba in NARROW:
        return f"{ba}はインが残りにくい狭水面で、まくりの土壌がある。"
    if it >= 60:
        return f"{ba}はイン有利の水面。外が崩すには相応の材料がいる。"
    if it >= 57:
        return f"{ba}はインがしっかり残りやすい水面。"
    if ba in SASHI:
        return f"{ba}はうねりで差しが効きやすく、内の一角にも目が向く。"
    if it <= 50:
        return f"{ba}はインが盤石とは言えず、外の仕掛けが通りやすい。"
    return f"{ba}は極端に偏らない水面で、スタートの流れがものを言う。"

# --- 検証用 引き算スコア（標準化＋等重み・仮置き）---
# 重み・閾値は検証ログのスコア相関を見てから調整する。
LV = {'A1': 4, 'A2': 3, 'B1': 2, 'B2': 1}
TH_KATA = 0.04    # スコア >= +0.04 → 堅め（5.3万件グリッド探索の最適値・場別上書きあり）
TH_HARAN = -0.09  # スコア <= -0.09 → 波乱（間は混戦）

# 場別チューニング（5.3万件で場別グリッド探索・下限ガードTK>=+0.02/TH<=-0.03）
# 出典：verify_log.csv 20250715-20260705 の全期間実測（2026-07-06反映）
BA_TH = {
    "桐生": (+0.03, -0.03),
    "戸田": (+0.08, -0.03),
    "江戸川": (+0.03, -0.03),
    "平和島": (+0.14, -0.07),
    "多摩川": (+0.02, -0.05),
    "浜名湖": (+0.11, -0.03),
    "蒲郡": (+0.03, -0.04),
    "常滑": (+0.04, -0.03),
    "津": (+0.05, -0.04),
    "三国": (+0.13, -0.03),
    "びわこ": (+0.11, -0.03),
    "住之江": (+0.17, -0.03),
    "尼崎": (+0.05, -0.03),
    "鳴門": (+0.04, -0.03),
    "丸亀": (+0.05, -0.03),
    "児島": (+0.11, -0.06),
    "宮島": (+0.08, -0.04),
    "徳山": (+0.04, -0.03),
    "下関": (+0.04, -0.05),
    "若松": (+0.08, -0.03),
    "芦屋": (+0.04, -0.04),
    "福岡": (+0.10, -0.05),
    "唐津": (+0.09, -0.03),
    "大村": (+0.07, -0.03),
}
def th_of(ba):
    return BA_TH.get(ba, (TH_KATA, TH_HARAN))

def f(x):
    try: return float(x)
    except: return 0.0

def nm(s): return s.replace('\u3000', '')

def motor_runs(v2, v3):
    """モーター2連率と3連率から走破数（分母）を逆算する。
    両方0%のときは「未走」と「走ったが2連対も3連対もない」を区別できないため None。
    120走まで探索し、両方の率と整合する最小の分母を返す。
    分母が大きいほど丸め誤差で一意に定まらず None になる。少走（分母が小さい）ケースを
    確実に拾うための関数であり、None は「十分に走っている」側に倒して扱う。"""
    try:
        a = float(v2 or 0); c = float(v3 or 0)
    except Exception:
        return None
    if a <= 0 and c <= 0:
        return None
    for n in range(1, 121):
        ok = True
        for v in (a, c):
            x = v * n / 100.0
            if abs(x - round(x)) > 0.004:
                ok = False
                break
        if ok:
            return n
    return None


def load_csv(path):
    with open(path, encoding='utf-8-sig') as fp:
        return list(csv.DictReader(fp))

def collect_toban(node, acc):
    """JSONを再帰的に走査して「登録番号」の値を集める。

    見どころJSONの構造（レース→艇→登録番号）に依存せず拾えるようにしておく。
    """
    if isinstance(node, dict):
        for k, v in node.items():
            if k == '登録番号' and isinstance(v, str) and v.strip():
                acc.add(v.strip())
            else:
                collect_toban(v, acc)
    elif isinstance(node, list):
        for v in node:
            collect_toban(v, acc)
    return acc

def write_racer_stats_today(now_iso):
    """見どころ4タブに登場する選手の成績JSONを docs/highlights/racerStatsToday.json に書く。

    収録対象は 当日/明日/前日/前々日 の4ファイルに登場する登録番号の和集合。
    未生成のファイルはスキップする（日によっては存在しない）。
    値は docs/data/racerStats.json のものをそのまま使う（丸め・型変換をしない）。
    racerStats.json に無い登番は収録せず、件数と一覧を標準出力に出す
    （index.html 側に「図鑑データが見つかりません」のフォールバックがあるため止めない）。
    """
    with open(RACER_STATS, encoding='utf-8') as sf:
        by_no = {p['no']: p for p in json.load(sf).get('players', [])}

    src_dir = os.path.dirname(STATS_OUT) or '.'
    union, sources, skipped = set(), {}, []
    for name in STATS_SOURCES:
        path = os.path.join(src_dir, name)
        try:
            with open(path, encoding='utf-8') as hf:
                found = collect_toban(json.load(hf), set())
        except Exception as e:
            # 読めなかったファイルは null で記録する。収録が静かに縮んだことを
            # 後から生成物だけで追えるようにするため。処理は止めない。
            sources[name] = None
            skipped.append("{}({})".format(name, e.__class__.__name__))
            continue
        sources[name] = len(found)
        union |= found
    print("収録元: " + " / ".join(
        "{}={}".format(n, '読めず' if c is None else c) for n, c in sources.items()))

    nos = sorted(union)
    players, missing = {}, []
    for no in nos:
        src = by_no.get(no)
        if src is None:
            missing.append(no)
            continue
        players[no] = {hk: src[sk] for hk, sk in PROF_KEYS}

    doc = {'asOf': 'unknown', 'generated': now_iso, 'sources': sources, 'players': players}
    os.makedirs(os.path.dirname(STATS_OUT) or '.', exist_ok=True)
    with open(STATS_OUT, 'w', encoding='utf-8') as sf:
        json.dump(doc, sf, ensure_ascii=False, separators=(',', ':'))

    if missing:
        print("NOTE: racerStats.json に無い登番 {}件（収録せず）: {}".format(
            len(missing), ','.join(missing)))
    # 読めないファイルがあると収録が静かに縮み、前日・前々日タブの選手情報が欠ける。
    # エラーにならず気づけないので、標準エラーに目立つ警告を出す（処理は止めない）。
    if skipped:
        print("WARNING: 見どころJSON {}/{}件が読めませんでした: {} → 収録が{}名に縮んでいます。"
              "前日・前々日タブで選手情報が欠ける可能性があります。".format(
                  len(skipped), len(STATS_SOURCES), ', '.join(skipped), len(players)),
              file=sys.stderr)
    print("OK: 見どころ登場{}名中{}名 → {}".format(len(nos), len(players), STATS_OUT))

def main():
    rac = load_csv(RACERS)

    # --- 2日混載CSV対策（案①）: 当日(JST)の開催日の行だけを処理対象にする ---
    # 夜間に翌日分がracers_today.csvへ追記されると (場名,レース) キーが両日で衝突し、
    # 両日に出る場のレースが12艇化して脱落 → 見どころが片日限定の少数場へ縮退する事故を防ぐ。
    _today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime('%Y%m%d')
    _days = sorted(set((r.get('開催日') or '').strip() for r in rac if (r.get('開催日') or '').strip()))

    if NEXT:
        # --- 翌日モード: 対象日 = 当日highlights.jsonの開催日より後で最小のCSV開催日 ---
        # 壁時計today+1でなくCSV基準にすることで0時跨ぎでも当日を確実に除外し翌開催日を指す。
        base_day = ''
        try:
            with open(OUT, encoding='utf-8') as _bf:
                base_day = (json.load(_bf).get('開催日') or '').strip()
        except Exception:
            base_day = ''
        if not base_day:
            base_day = _today  # フォールバック: 当日highlightsが読めなければ壁時計今日を基準
        _future = [d for d in _days if d > base_day]
        if not _future:
            print("SKIP(翌日): 当日開催日{}より後のCSV開催日が無い（翌日未到着）。既存 highlights_next を保持（上書きせず）"
                  .format(base_day))
            return
        _target = _future[0]
        rac = [r for r in rac if (r.get('開催日') or '').strip() == _target]
        print("翌日モード: 基準日{} → 対象開催日{}（{}行）".format(base_day, _target, len(rac)))
    else:
        if len(_days) > 1:
            print("NOTE: CSVに複数開催日が混在: {} → 当日{}の行のみ処理".format(_days, _today))
        _rac_today = [r for r in rac if (r.get('開催日') or '').strip() == _today]
        if not _rac_today:
            # (a) 当日分が0行なら既存highlights・predictionsを上書きせずスキップ（朝の正生成を夜の空振りで壊さない）
            print("SKIP: 当日{}の出走表行が0（CSV開催日={}）。既存highlights・predictionsを保持（上書きせず）"
                  .format(_today, _days))
            return
        rac = _rac_today

    try:
        mot = load_csv(MOTORS)
    except Exception:
        mot = []
    mkey = {(m['場コード'], m['登録番号']): f(m['モーター2連対率']) for m in mot}

    # 〔今節の展示タイム偏差〕docs/data/motorParts.json から、当日より前の同じ場の展示タイムを拾う。
    #   生の秒数は水面・気象で基準が動くため出さない。そのレースの6艇平均からの差だけを使う。
    #   遡る日数は出走表の「1日目成績〜6日目成績」の埋まり本数＝前日までに走った日数で決める。
    #   これにより前節を跨がない（motorParts の「節名」は全行が空のため、節の区切りに使えない）。
    _DAYCOLS = ['1日目成績', '2日目成績', '3日目成績', '4日目成績', '5日目成績', '6日目成績']
    _tenji = {}
    try:
        with open(os.path.join('docs', 'data', 'motorParts.json'), encoding='utf-8') as _mf:
            _mprec = json.load(_mf).get('records', [])
        _byrace = defaultdict(list)
        for _x in _mprec:
            _byrace[(_x.get('jcd'), _x.get('開催日'), _x.get('rno'))].append(_x)
        _acc = defaultdict(list)
        for _k, _v in _byrace.items():
            _ts = []
            for _x in _v:
                _t = f(_x.get('展示タイム'))
                if _t > 0:
                    _ts.append(_t)
            if len(_ts) < 4:          # 6艇平均が作れないレースは使わない
                continue
            _avg = sum(_ts) / len(_ts)
            for _x in _v:
                _t = f(_x.get('展示タイム'))
                if _t > 0:
                    _acc[(_x.get('jcd'), str(_x.get('登番')))].append((_x.get('開催日'), round(_t - _avg, 3)))
        _tenji = _acc
    except Exception:
        _tenji = {}

    def tenji_dev(r, hd):
        """今節の展示タイム偏差。(平均偏差, 本数) を返す。取れなければ (None, 0)。
           マイナスほど6艇平均より速い。本数は必ず読者に併記する。"""
        n = sum(1 for c in _DAYCOLS if (r.get(c) or '').strip())
        if n <= 0:
            return None, 0
        h = _tenji.get((r['場コード'], str(r['登録番号'])), [])
        h = sorted([x for x in h if x[0] < hd], reverse=True)[:n]
        if len(h) < 1:                # 0本（初日）は出せない。1本以上あれば偏差を出す。
            # 偏差は「同じレースの6艇平均との差」なので、その日の水面・気象条件は定義上キャンセルされている。
            # 1本でも事実として正しい。本数を必ず併記して読者が判断できるようにする。
            return None, len(h)
        return round(sum(d for _, d in h) / len(h), 3), len(h)

    def setsu_trail(r):
        """今節の走り（前日まで）。出走表の「N日目成績」から着順・ST・進入コースを取り出す。
           書式は 'レース番号R/着/ST/進入コース' で、1日に複数走ある場合は半角スペース区切り。
           例 '3R/5/.12/6 7R/2/.11/1' → 3R5着ST.12を6コース、7R2着ST.11を1コース。
           返すのは [{日:1, レース:'3R', 着:5, ST:'.12', コース:6}, ...]。取れなければ []。"""
        out = []
        for di, c in enumerate(_DAYCOLS, start=1):
            v = (r.get(c) or '').strip()
            if not v:
                continue
            for tok in v.split():
                p = tok.split('/')
                if len(p) != 4:
                    continue          # 書式が違う行は捨てる（無理に解釈しない）
                try:
                    _chaku = int(p[1])
                except ValueError:
                    _chaku = None     # F・L・失格などは数値にならない。原文を着に入れる
                out.append({'日': di, 'レース': p[0],
                            '着': _chaku if _chaku is not None else p[1],
                            'ST': p[2], 'コース': p[3]})
        return out

    # 選手別①1着率（buildRacerInRate.py 出力）。下振れ要因の事実提示に使う（スコアには非関与）。
    try:
        with open(os.path.join('docs', 'data', 'racerInRate.json'), encoding='utf-8') as _rf:
            _rj = json.load(_rf)
            _inrate = _rj.get('racers', {})
            _inrate_updated = _rj.get('updated', '')
    except Exception:
        _inrate = {}
        _inrate_updated = ''
    # 見立ての比較基準：1コース1着率を持つ選手全体の中央値（母数ガードは racerInRate 側で済み）。
    # 固定値を書かず毎回算出する。単独の数字を置かないための「真ん中」を作るだけで、判定には非関与。
    try:
        _rates_all = sorted(v['rate'] for v in _inrate.values() if v.get('rate') is not None)
        _n_rate = len(_rates_all)
        _med_rate = (round((_rates_all[_n_rate // 2 - 1] + _rates_all[_n_rate // 2]) / 2, 1)
                     if _n_rate % 2 == 0 else round(_rates_all[_n_rate // 2], 1)) if _n_rate else None
    except Exception:
        _n_rate, _med_rate = 0, None
    # ①着外率20%以上の場（jcd）：02戸田/14鳴門/04平和島/01桐生/03江戸川/10三国
    _DOWN_VENUES = {'01', '02', '03', '04', '10', '14'}
    # ①が崩れる時の「崩れ方」場別分布（buildCollapsePattern.py 出力）。事実提示のみ・スコア非関与。
    try:
        with open(os.path.join('docs', 'data', 'collapsePattern.json'), encoding='utf-8') as _cf:
            _collapse = json.load(_cf).get('venues', {})
    except Exception:
        _collapse = {}

    # --- 検証スコア用 正規化（当日全出走者でmin-max・等重み）---
    def loc_or_nat(r):
        l = f(r['当地勝率']); return l if l > 0 else f(r['全国勝率'])
    _lv = [LV.get(r['級別'], 1) for r in rac]
    _loc = [loc_or_nat(r) for r in rac]
    _st = [f(r['平均ST']) for r in rac]
    _mtp = [v for v in (mkey.get((r['場コード'], r['登録番号']), 0.0) for r in rac) if v > 0]
    lv_lo, lv_hi = (min(_lv), max(_lv)) if _lv else (1, 4)
    loc_lo, loc_hi = (min(_loc), max(_loc)) if _loc else (0.0, 1.0)
    st_lo, st_hi = (min(_st), max(_st)) if _st else (0.1, 0.3)
    mt_lo, mt_hi = (min(_mtp), max(_mtp)) if _mtp else (0.0, 1.0)
    def _nz(v, lo, hi): return (v - lo) / (hi - lo) if hi > lo else 0.5
    def total_power(r):
        parts = [_nz(LV.get(r['級別'], 1), lv_lo, lv_hi),
                 _nz(loc_or_nat(r), loc_lo, loc_hi),
                 1 - _nz(f(r['平均ST']), st_lo, st_hi)]  # STは速い(小)ほど良い→反転
        mv = mkey.get((r['場コード'], r['登録番号']), 0.0)
        if mv > 0: parts.append(_nz(mv, mt_lo, mt_hi))
        return sum(parts) / len(parts)
    # 検証スコアの要素別内訳（total_powerと同じ_nz・同じ反転を再利用。値は変えない）。
    # 波乱判別力の要素別解剖用。モーターは値>0のときのみ数値、無ければNone。
    def power_vec(r):
        lv = _nz(LV.get(r['級別'], 1), lv_lo, lv_hi)
        lc = _nz(loc_or_nat(r), loc_lo, loc_hi)
        stv = 1 - _nz(f(r['平均ST']), st_lo, st_hi)
        mvr = mkey.get((r['場コード'], r['登録番号']), 0.0)
        mt = _nz(mvr, mt_lo, mt_hi) if mvr > 0 else None
        return {'級別': round(lv, 4), '当地': round(lc, 4), 'ST': round(stv, 4),
                'モーター': (round(mt, 4) if mt is not None else None)}

    # 図鑑の決まり手CSVから やられ系（さされ・まくられ・まくりさされ）を読む。
    # 旧フォーマット（列が無い）やファイル欠損でも落ちないようにする。
    def fr(x):
        try:
            return float(x)
        except Exception:
            return None
    yarare = {}
    try:
        def _iv(x):
            try:
                return int(x)
            except Exception:
                return None
        for k in load_csv(KIM):
            in1 = k.get('イン進入数', '')
            try:
                in1 = int(in1)
            except Exception:
                in1 = 0
            yarare[k['登録番号']] = {
                'さされ率': fr(k.get('さされ率', '')),
                'まくられ率': fr(k.get('まくられ率', '')),
                'まくりさされ率': fr(k.get('まくりさされ率', '')),
                'イン数': in1,
                'まくり率': fr(k.get('まくり率', '')),
                '差し率': fr(k.get('差し率', '')),
                '1着数': _iv(k.get('1着数', '')),          # B案の母数ガード・分母表示用
                'まくり数': _iv(k.get('まくり', '')),        # まくり1着数（生カウント）
                '差し数': _iv(k.get('差し', '')),            # 差し1着数（生カウント）
            }
    except Exception:
        yarare = {}
    # 場ごと0%率でモーター使用可否
    zero = defaultdict(lambda: [0, 0])
    for m in mot:
        zero[m['場名']][1] += 1
        if f(m['モーター2連対率']) == 0: zero[m['場名']][0] += 1
    motok = {k: (z/t < 0.4) for k, (z, t) in zero.items()}

    for r in rac:
        r['_mtr'] = mkey.get((r['場コード'], r['登録番号']), 0.0)

    # 決まり手タイプ（まくり型/差し型/標準）。データ欠損はNone。
    def kim_type(toban):
        y = yarare.get(toban, {})
        mk = y.get('まくり率'); sa = y.get('差し率')
        if mk is None and sa is None: return None
        mk = mk or 0.0; sa = sa or 0.0
        if mk >= 25 and mk >= sa + 8: return 'makuri'
        if sa >= 30 and sa >= mk + 8: return 'sashi'
        return None

    # 天候（表示だけ：締切時刻に最も近い時刻の風をweather.jsonから引く。結論は書かない）
    wjson = {}
    try:
        with open(WEATHER, encoding='utf-8') as wf:
            wjson = json.load(wf).get('stadiums', {})
    except Exception:
        wjson = {}

    def wind_line(jcd, hhmm):
        """締切HH:MMに最も近い時刻の風の事実を1行返す。取れなければ空文字。"""
        st = wjson.get(str(jcd).zfill(2))
        if not st or not hhmm or ':' not in hhmm:
            return ''
        try:
            target = int(hhmm.split(':')[0]) * 60 + int(hhmm.split(':')[1])
        except Exception:
            return ''
        best = None; bd = 1e9
        for h in st.get('hourly', []):
            t = h.get('time', '')
            if 'T' not in t:
                continue
            hm = t.split('T')[1][:5]
            try:
                cur = int(hm.split(':')[0]) * 60 + int(hm.split(':')[1])
            except Exception:
                continue
            dd = abs(cur - target)
            if dd < bd:
                bd = dd; best = h
        if not best:
            return ''
        wind = best.get('wind'); d = best.get('dir', ''); wx = best.get('wx', '')
        if wind is None:
            return ''
        # 事実の描写のみ。有利不利の結論には踏み込まない。
        wxs = f"{wx}天で" if wx and wx not in ('晴',) else ''
        if wind < 3:
            return f"当日は{wxs}{d}の風{wind:.0f}m前後と穏やかで、水面は落ち着いた条件。"
        elif wind < 5:
            return f"当日は{wxs}{d}の風{wind:.0f}m。スタート隊形に影響しうる風速。"
        elif wind < 7:
            return f"当日は{wxs}{d}の風{wind:.0f}mとやや強く、水面は波立ちやすい。"
        else:
            return f"当日は{wxs}{d}の風{wind:.0f}mの強風で、水面は落ち着かない。"

    races = defaultdict(list)
    for r in rac:
        races[(r['場名'], r['レース'])].append(r)

    out_races = []
    pred_list = []
    # 部分成功許容：1レース(場)分の生成を関数に切り出し、呼び出し側で例外を握る。
    # 一部の場/レースが壊れても「取れた分だけ」出力し、失敗はログする（全滅時のみ点1の自己検査で非ゼロ）。
    def _one(ba, rc, bo):
        if len(bo) != 6: return None
        bo.sort(key=lambda b: int(b['枠']))
        # --- 検証ログ：①総合力 − ④総合力（標準化・等重み）---
        diff = round(total_power(bo[0]) - total_power(bo[3]), 3)
        # 要素別内訳（①④の各要素値と差。波乱判別力の要素解剖用・既存diffは不変）
        _p1 = power_vec(bo[0]); _p4 = power_vec(bo[3])
        def _br(k):
            a = _p1[k]; b = _p4[k]
            return {'①': a, '④': b, '差': (None if a is None or b is None else round(a - b, 3))}
        score_breakdown = {'級別': _br('級別'), '当地': _br('当地'), 'ST': _br('ST'),
                           'モーター': _br('モーター'),
                           'モーター有無': {'①': _p1['モーター'] is not None,
                                       '④': _p4['モーター'] is not None}}
        tk_ba, th_ba = th_of(ba)
        if diff >= tk_ba:
            verdict, hero = '堅め', 1
        elif diff <= th_ba:
            verdict, hero = '波乱', 4
        else:
            verdict, hero = '混戦', None  # 混戦の主役は下で機力→実力→決まり手で判断
        it = INTOP.get(ba, 53)
        use_m = motok.get(ba, True)
        mt = [b['_mtr'] for b in bo]
        # 表示用：出走表CSVの当日値を使う。motors_all.csv は場によって開催日が古く照合できない。
        _mv2 = [f(x.get('モーター2連率')) for x in bo]
        _valid2 = [v for v in _mv2 if v > 0]
        mavg2 = sum(_valid2) / len(_valid2) if _valid2 else None
        valid = [v for v in mt if v > 0]
        mavg = sum(valid)/len(valid) if valid else None
        hi = lambda v: use_m and mavg and v > 0 and v > mavg+5
        lo = lambda v: use_m and mavg and v > 0 and v < mavg-5

        in1 = bo[0]; il = f(in1['当地勝率']); ina = f(in1['全国勝率'])
        inA = in1['級別'] in ('A1', 'A2')
        in_lo = lo(mt[0])
        in_strong = inA and il > ina and il > 0 and not in_lo
        inB = in1['級別'] in ('B1', 'B2')
        # ①不安の判定（全場共通）：
        #  ・B級インは不安。
        #  ・A級インは当地見劣り単独では不安にしない（格が担保）。機力下位のときだけ不安。
        #  ・イン天国(it>=60)ではB級のみ不安（機力下位でも水面が残す）。
        if it >= 60:
            in_weak = inB
        elif inA:
            in_weak = in_lo
        else:
            in_weak = inB or (il > 0 and il < ina) or in_lo

        seeds = 0
        if in_weak: seeds += 1
        threats = []; out_hi = False
        LVRANK = {'A1': 4, 'A2': 3, 'B1': 2, 'B2': 1}
        for i, b in enumerate(bo):
            w = int(b['枠']); lv = b['級別']; loc = f(b['当地勝率']); nat = f(b['全国勝率']); st = f(b['平均ST'])
            n2 = f(b['全国2連率'])
            a_out = w >= 4 and lv in ('A1', 'A2')
            local_out = w >= 3 and loc > 0 and loc > nat
            if a_out or local_out:
                seeds += 1
                threats.append({'w': w, 'lv': lv, 'st': st, 'a_out': a_out,
                                'local_out': local_out, 'mhi': hi(mt[i]), 'nm': nm(b['氏名']),
                                'lvr': LVRANK.get(lv, 0), 'loc': loc,
                                'mlo': lo(mt[i]), 'n2': n2})
            if w >= 4 and hi(mt[i]): out_hi = True
        if in_lo and out_hi: seeds += 1

        # 混戦の主役を①と④で判断（機力差→実力(当地)差→決まり手）
        if hero is None:
            # 混戦の主役は①固定。逆算実測(20250715-20260705)：混戦で④に主役を振った
            # 条件(機力+8/当地+1.0/まくり型狭水面)でも④の1着率は9.6%・3着内45.8%に留まり、
            # 同レースの①は1着53.9%・3着内81.0%。④選定は誤りのため①へ据える。
            # （④の脅威は見出し/展開/波及で別途言及するので物語は損なわない）
            hero = 1
        if it >= 60: seeds = max(0, seeds-1)
        elif it <= 50: seeds += 1
        if ba in MAKURI: seeds += 1

        # ①(bo[0])の下振れ要因の事実提示（スコア・判定には非関与・追加のみ）。※見出し/波及の書き分けで参照するため前倒しで算出。
        #   条件1 ①のinWinRate<15（nullは判定対象外）／条件2 ①の機力<25／条件3 当場が①着外率20%以上
        _df_items = []
        _in1_rate = (_inrate.get(bo[0]['登録番号']) or {}).get('rate')
        if _in1_rate is not None and _in1_rate < 15:
            _df_items.append("①の1着率 {}%".format(_in1_rate))
        _in1_mtr = bo[0]['_mtr'] if (use_m and bo[0]['_mtr'] > 0) else None
        if _in1_mtr is not None and _in1_mtr < 25:
            _df_items.append("①のモーター2連率 {}%".format(round(_in1_mtr, 1)))
        if bo[0]['場コード'] in _DOWN_VENUES:
            _df_items.append("当場は①着外率20%以上（{}）".format(ba))
        downFactors = {'count': len(_df_items), 'items': _df_items}
        # 見立ての「名指し」用は①自身の選手要因(1着率/機力)のみ（downFactors本体は無改変）。
        # 場の条件(当場が①着外率20%以上)は場ごと固定で全レース同文になり事実ブロックにも既出のため、
        # 見立てには書かない（downFactorsの判定・count・事実ブロック表示はそのまま）。
        _pf = []   # 選手属性（同一主語①で「に加え」連結可）
        if _in1_rate is not None and _in1_rate < 15:
            _pf.append("1着率{}%".format(_in1_rate))
        if _in1_mtr is not None and _in1_mtr < 25:
            _pf.append("機力{}%".format(round(_in1_mtr)))

        # --- 見立て見出し（scoreトーン×主役、断定しない。downFactorsで“崩れる理由”を書き分け） ---
        # score(diff)で①中心/難解/外主役のトーンを決め、その上に主役艇名を乗せる。判定・diffには非関与。
        o4 = sorted([t for t in threats if t['w'] >= 4], key=lambda x: x['w'])
        inn = sorted([t for t in threats if t['w'] < 4], key=lambda x: x['w'])
        # 見出しの外主役はスコア順（カド⑤が④より上位スコアなら⑤主役文）。判定(hero/verdict)・スコアは不変。
        o4s = sorted(o4, key=lambda t: -total_power(bo[t['w']-1]))
        mid_hi_w = [w for w in (2, 3) if hi(mt[w-1])]   # 機力上位の中団②③
        head_w = None
        def _kt_of(w):
            return kim_type(bo[w-1]['登録番号'])
        # 述語は「連絡み」寄り（実測: 波乱④は1着20.6%/3着内61.1%＝勝ち切りは薄く連絡みが実態）。
        # 決まり手×場特性で分岐。語感刷新分は新ID(H4-6/M8-10/N1)で検証追跡できるよう振り直す。
        def _out_pred(t, strong):
            w = t['w']; kt = _kt_of(w)
            if kt == 'makuri' and (ba in NARROW or ba in MAKURI):
                return ('のまくりが狭水面で連を脅かす', 'H4' if strong else 'M8')
            if kt == 'sashi':
                return ('のまくり差しが連に食い込む', 'H5' if strong else 'M9')
            if t.get('mhi'):
                return ('は機力上位で連軸を脅かす', 'H6' if strong else 'M10')
            if w == 4:
                return ('はカドから連に押し込む形', 'H7' if strong else 'M11')
            return ('はダッシュから連絡み、連軸を脅かす', 'H8' if strong else 'M12')
        # downFactorsで“①が崩れる理由”を書き分ける（判定・head_w・述語は不変。文面/IDのみ）。
        #   0個=①自体に材料薄い→理由を相手側に置く(M14)／1個=要因を名指し(M15)／2個+=要因を重ねる(M16)。
        # 「①に不安」の断定を廃し、下振れ要因ゼロのレースでは“不安”を書かない（事実ブロックと整合）。
        n1h = nm(in1['氏名'])
        # 見立ての書き分けは「①自身の選手要因(_pf: 1着率/機力)」のみで行う。場の条件(_vf)は
        # 場ごと・その日ごとに固定で全レース同文になり、かつ事実ブロックに既出のため、見立てには書かない。
        # 原則: レースごとに変わる要素（相手艇・述語・①の実数）を先に置き、固定情報は事実ブロックで1回だけ。
        # M14（①自身に崩れる材料が薄く、外に脅威）の構文分散。言い換えでなく主語・語順を変える。
        #   A=①主語／B=相手主語／C=①の1着率を出す(inWinRate有時)／D=①の機力を出す(機力上位帯時)。
        #   場内で直前2つと同じ型を避け、決定的に選ぶ（無ければA/B交互）。情報量も増える(C/D)。
        _m14_hi = (use_m and bo[0]['_mtr'] > 0 and hi(mt[0]))
        _m14_mv = round(bo[0]['_mtr']) if (use_m and bo[0]['_mtr'] > 0) else None
        # ★見立ての基幹（2026-08-19 改稿）。構文ローテを廃止し、①の実数を必ず1つ置く。
        #   単独の数字を出さないため、全選手の中央値との差を同じ文に入れる（比較対象を同じ視野に）。
        #   数字が毎レース変わるため、構文が1つでも同一文にはならない。
        def _in1_fact():
            """①の実数を返す。(文, 帯) 帯は 'hi'/'mid'/'lo'/'mtr'/None。
               表層は実数と分母のみ。全体の真ん中との比較は深層に置く（単独の数字を置かないための対比）。
               帯は語順の決定にだけ使い、文面には出さない。"""
            lvs = f"（{in1['級別']}）"
            if _in1_rate is not None and _med_rate is not None:
                d = _in1_rate - _med_rate
                n = (_inrate.get(bo[0]['登録番号']) or {}).get('inN')
                nn = f"（{n}走）" if n else ""
                band = 'mid' if abs(d) < 3 else ('hi' if d > 0 else 'lo')
                return f"①{n1h}{lvs}の1コース1着率は{round(_in1_rate)}%{nn}", band
            if _m14_mv is not None and mavg2:
                return f"①{n1h}{lvs}のモーター2連率は{_m14_mv}%（場平均{round(mavg2)}%）", 'mtr'
            return None, None
        def _lay(rival):
            """①の値域で語順を決める。高い＝①先／並み・低い＝相手先。
               ①が疑わしいレースは相手が主役なので、語順が意味と一致する。
               ローテを使わないため表示順に依存せず、値が毎レース変わるので書き出しも散る。"""
            f1, band = _in1_fact()
            if not f1:
                return f"{rival}。①{n1h}は1コース進入の走数が足りず率を出せない"
            if band in ('mid', 'lo'):
                return f"{rival}。{f1}"
            return f"{f1}。{rival}"
        def _m14(rival):
            return _lay(rival), 'M14'
        def _dekata(rv):
            return _lay(rv)
        def _fuan(rival):
            # 下振れ要因があるレースも語順分岐は共通。機力の要因だけ一言を添える。
            f1, band = _in1_fact()
            if not f1:
                return _m14(rival)
            # 機力の一言は表層に置かない（結論が2つになるため）。深層の事実ブロックに既出。
            return _lay(rival), ('M16' if any(x.startswith('機力') for x in _pf) else 'M15')
        def _k5rk():
            return f"{K[o4s[0]['w']-1]}{o4s[0]['nm']}" if o4s else "外"
        if in_strong and diff >= tk_ba:
            if downFactors['count'] == 0:
                headline = _lay(f"相手を{_k5rk()}に求める形"); hid = 'K5'
            elif diff >= 0.30:
                headline = _lay("相手探しの一戦"); hid = 'K1'
            elif it >= 60:
                headline = _lay("水面も後押しする形"); hid = 'K2'
            else:
                headline = _lay("外の一発をどこまで測るか"); hid = 'K3'
        elif o4 and ((in_weak and diff <= th_ba) or (in_strong and verdict == '波乱')):
            # 波乱×外主役（①不安 or in_strongでも④優勢）。述語は連絡み寄り。カド⑤優位なら⑤主役。
            w0 = o4s[0]; suf, _ = _out_pred(w0, True)
            headline, hid = _fuan(f"{K[w0['w']-1]}{w0['nm']}{suf}")
            head_w = w0['w']
        elif in_strong:
            if downFactors['count'] == 0:
                headline = _lay(f"相手を{_k5rk()}に求める形"); hid = 'K5'
            else:
                headline = _lay("外の一発をどこまで測るか"); hid = 'K4'
        elif in_weak and o4:
            # 混戦寄り×外主役。連絡み寄りの主役候補文。カド⑤優位なら⑤主役。
            w0 = o4s[0]; suf, _ = _out_pred(w0, False)
            headline, hid = _fuan(f"{K[w0['w']-1]}{w0['nm']}{suf}")
            head_w = w0['w']
        elif in_weak and mid_hi_w:
            # 機力上位の中団②③が連に突け入る（実装テーブル：中団警戒）
            mw = mid_hi_w[0]
            headline, hid = _fuan(f"{K[mw-1]}{nm(bo[mw-1]['氏名'])}の機力上位が中団から連に突け入る")
            head_w = mw
        elif in_weak and inn:
            headline, hid = _fuan(f"{K[inn[0]['w']-1]}{inn[0]['nm']}の差しが突け入る一戦")
            head_w = inn[0]['w']
        elif in_weak:
            headline, hid = _fuan("外の仕掛け待ちで波乱含み")
        elif o4:
            w0 = o4s[0]; head_w = w0['w']
            if w0.get('mhi'):
                _rv = f"{K[w0['w']-1]}{w0['nm']}の機力上位が連に絡む余地"
            else:
                _rv = f"{K[w0['w']-1]}{w0['nm']}のまくりが連に絡む余地"
            # 「①の出方ひとつ」は downFactors=0 のときのみ許容。選手要因があれば名指し(M15/M16)、
            # 場のみ該当（_pf空でdf>=1）は場を書かず相手側へ(M14相当)。場の条件は見立てに書かない。
            if downFactors['count'] == 0:
                headline = _dekata(_rv); hid = ('M13' if w0.get('mhi') else 'M6')
            elif not _pf:
                headline, hid = _m14(_rv)   # 場のみ該当も M14 として構文分散＋場内ローテーション
            elif len(_pf) == 1:
                headline = f"①{n1h}は{_pf[0]}。{_rv}"; hid = 'M15'
            else:
                headline = f"①{n1h}は{_pf[0]}に加え{_pf[1]}。{_rv}"; hid = 'M16'
        else:
            headline = _lay("軸を絞りにくい一戦"); hid = 'M7'

        # --- 展開の筋（記者文型：場特性→①〜したい〜だが→主役決まり手×場特性→死角）---
        tenkai = []
        # 〔場〕1行目に場特性（実装テーブルA①）
        # 〔場特性〕2026-08-19 廃止。1場12レースが完全な同一文になり、今日の判断が変わらないため。
        #   水面の傾向は /stadium/（24場特性）に常設。ここでは書かない。
        # 〔天候〕締切時刻の風の事実を1行（表示だけ・結論は書かない）
        wl_line = wind_line(bo[0]['場コード'], bo[0].get('締切時刻', ''))
        if wl_line:
            tenkai.append(wl_line)

        # 〔軸〕①を記者表現で（主語を必ず書く／実数を先、評価を後／短く切る）。
        #   2026-08-19 改稿：主語の欠けた条件節（「先マイを許さなければ」等）を全廃した。
        m1 = '機力は場上位' if hi(mt[0]) else '機力は場下位' if lo(mt[0]) else ('機力は場平均並み' if use_m and mt[0] > 0 else '')
        in_f = int(in1['F数']) >= 1
        in_kt = kim_type(in1['登録番号'])
        _in_no = f"①{nm(in1['氏名'])}"
        _in_num = (f"1コース1着率{round(_in1_rate)}%（{(_inrate.get(in1['登録番号']) or {}).get('inN')}走）"
                   if _in1_rate is not None else f"当地{il:.2f}")
        if in_strong:
            if diff >= 0.30:
                tenkai.append(f"{_in_no}は{in1['級別']}で{_in_num}。{('で'+m1)[1:] if m1 else '当地は全国を上回る'}。①のSが五分なら、主導権は譲るまい。")
            else:
                tenkai.append(f"逃げたい{_in_no}は{in1['級別']}で{_in_num}。②③が壁を作れば、①は主導権を譲りにくい。")
        elif in_weak:
            why = []
            if not inA: why.append('格')
            if il > 0 and il < ina: why.append('当地')
            if in_lo: why.append('機力')
            fnote = 'F持ちで踏み込みにくい。' if in_f else ''
            _upA = [K[int(b['枠'])-1] for b in bo[1:] if b['級別'] in ('A1', 'A2')]
            _upS = ('・'.join(_upA) + 'がA級。') if _upA else ''
            tenkai.append(f"逃げたい{_in_no}だが{in1['級別']}で{_in_num}。{_upS}{fnote}①に先マイを許さなければ、主導権は外へ。")
        else:
            tenkai.append(f"逃げたい{_in_no}は{in1['級別']}で{_in_num}。①のSが決まれば逃げ。①が遅れれば、外に隙。")

        # 〔主役〕見出しの主役艇を先頭に、次点はST順（見出しと展開のズレを防ぐ）
        th_sorted = sorted(threats, key=lambda t: (t['st'] if t['st'] > 0 else 9, t['w']))
        if head_w is not None:
            head_t = [t for t in threats if t['w'] == head_w]
            rest = [t for t in th_sorted if t['w'] != head_w]
            th2 = (head_t + rest)[:2]
        else:
            th2 = th_sorted[:2]
        toban_by_w = {int(b['枠']): b['登録番号'] for b in bo}
        # 全艇の格・当地の最上位を把握（格上艇が主役でない理由づけに使う）
        LVRANK2 = {'A1': 4, 'A2': 3, 'B1': 2, 'B2': 1}
        boat_meta = {int(b['枠']): {'lvr': LVRANK2.get(b['級別'], 0), 'lv': b['級別'],
                                    'loc': f(b['当地勝率']), 'nm': nm(b['氏名'])} for b in bo}
        used_shuyaku = False  # 「主役になりうる」を1レース1回に制限
        head_w0 = th2[0]['w'] if th2 else None
        for idx, t in enumerate(th2):
            role = '外枠のダッシュ勢' if t['w'] >= 4 else '内寄りの一角'
            ex = []
            if t['local_out']: ex.append('当地巧者')
            if t['a_out']: ex.append('A級')
            if t['mhi']: ex.append('機力上位')
            if t['st'] > 0 and t['st'] <= 0.15: ex.append('鋭ST')
            exs = ('（'+'・'.join(ex)+'）') if ex else ''
            kt = kim_type(toban_by_w.get(t['w'], ''))
            fit = ''
            if t['w'] >= 4:
                base_kim = 'まくり差し' if kt == 'sashi' else 'まくり'
                if kt == 'makuri':
                    if ba in NARROW: fit = 'まくり型で狭水面と噛み合い、'
                    elif it >= 58:   fit = 'まくり型だが差しの利く水面で割り引きたく、'
                    else:            fit = 'まくり型の持ち味を出しやすく、'
                elif kt == 'sashi':
                    fit = '差し型で、内が動いた隙を突く形なら、'
            else:
                base_kim = '差し・まくり差し'
                if kt == 'sashi':
                    fit = '差し型が水を得やすく、'
                elif kt == 'makuri':
                    fit = 'まくり型で一発の破壊力があり、'
            _tb = bo[t['w'] - 1]
            _ty2 = yarare.get(_tb['登録番号'], {}) or {}
            _tw = _ty2.get('1着数')
            # 〔着眼点の2層決定〕第1層＝場のデフォルト、第2層＝そのレースの状態で上書き。
            #   上書きは例外扱い。閾値25ptは本日実測の分布（中央値15.5・80%点24.5）から取った。
            #   もともと機力を主材料にする場（motorFirst）は上書きしても変わらないため対象外。
            _mts = [b.get('_mtr', 0) for b in bo if b.get('_mtr', 0) > 0]
            _mgap = (max(_mts) - min(_mts)) if len(_mts) >= 4 else 0
            _focus = VENUE_FOCUS.get(ba, 'gapFirst')
            if _mgap >= 25 and _focus != 'motorFirst':
                _focus = 'motorFirst'
            _tm = _tb.get('_mtr', 0) if use_m else 0
            _num_key = 'まくり数' if t['w'] >= 4 else '差し数'
            _num_lbl = 'まくり' if t['w'] >= 4 else '差し'
            _nv = _ty2.get(_num_key)
            _f_kim = f"1着{_tw}本のうち{_nv}本が{_num_lbl}" if (_tw and _tw >= 10 and _nv is not None) else None
            _f_mtr = f"モーター2連率{round(_tm)}%（場平均{round(mavg2)}%）" if (_tm > 0 and mavg2) else None
            _f_loc = f"当地{f(_tb['当地勝率']):.2f}"
            _order = {'motorFirst':    [_f_mtr, _f_kim, _f_loc],
                      'collapseFirst': [_f_kim, _f_mtr, _f_loc],
                      'gapFirst':      [_f_loc, _f_kim, _f_mtr]}[_focus]
            _facts = next(x for x in _order if x)
            _st = f"、平均ST{_tb['平均ST']}" if t['st'] > 0 else ""
            _bno = f"{K[t['w']-1]}{t['nm']}"
            if idx == 0:
                tenkai.append(f"対抗は{_bno}。{_tb['級別']}で{_facts}{_st}。{K[t['w']-1]}のSが決まれば{base_kim}。")
                used_shuyaku = True
                # 実力上位でも今節機が下位なら、機力を材料に切り替えて一言
                if t.get('mlo') and t.get('n2', 0) >= 35 and use_m:
                    tenkai.append(f"ただ{K[t['w']-1]}は全国2連率{round(t['n2'])}%に対し、今節機は{round(_tm)}%。")
            else:
                pred2 = 'まくり差し' if t['w'] >= 4 else '差し'
                tenkai.append(f"{_bno}も侮れない。{_tb['級別']}で{_facts}。{K[t['w']-1]}は{pred2}から連に。")

        # 修正1：主役より格上・当地上位の艇がいれば、主役でない理由を一言添える
        mentioned_w = {t['w'] for t in th2}
        if head_w0 is not None:
            main_meta = boat_meta.get(head_w0, {})
            # 明確な格上のみ：級が1段以上上、または同格で当地が1.0以上上（僅差では言わない）
            # ※展開で既に言及した艇（二番手含む）は除外＝同一艇の二重言及バグ修正
            supers = [w for w, mm in boat_meta.items() if w not in mentioned_w and w != 1 and (
                mm['lvr'] > main_meta.get('lvr', 0) or
                (mm['lvr'] == main_meta.get('lvr', 0) and mm['loc'] > main_meta.get('loc', 0) + 1.0))]
            # 主役より級が下または同格なら「地力最上位」とは言わない
            supers = [w for w in supers if boat_meta[w]['lvr'] >= main_meta.get('lvr', 0)]
            if supers:
                sw = sorted(supers, key=lambda w: (-boat_meta[w]['lvr'], -boat_meta[w]['loc']))[0]
                sm = boat_meta[sw]
                # A級のみ「地力最上位/上位」と表現。非A級は控えめに
                if sm['lv'] in ('A1', 'A2'):
                    if sw <= 3:
                        tenkai.append(f"{K[sw-1]}{sm['nm']}は{sm['lv']}で地力最上位だが、内寄りで一撃の形を作りにくく、Sの決まった主役に主導権を譲る形。")
                    else:
                        tenkai.append(f"{K[sw-1]}{sm['nm']}は{sm['lv']}で地力上位だが、進入位置で分があるのは主役側。")

        # 〔混戦の痩せ対策〕言及すべき対抗が拾えなかったレースでも、主役側の一文を必ず置く
        if not th2:
            if hero == 4:
                tenkai.append(f"対するカド④{nm(bo[3]['氏名'])}。目立つ材料は薄いが、Sひとつで景色の変わる位置ではある。")
            else:
                tenkai.append("相手は横一線。②の差し、④のダッシュと、二番手争いは展示の気配次第。")

        # 〔死角〕必ず1つ（実装テーブルA④：F・級・機力から。同文を避け条件で散らす）
        saten = None; skw = None; sid = None
        # f_out：カド勢(w>=4)のF持ち。A級を優先、カドF単独(5のみ/6のみ)は死角として弱く除外
        _fout_all = [t for t in threats if t['w'] >= 4 and int(bo[t['w']-1]['F数']) >= 1]
        # A級F艇を最内優先、次に非A級F艇を最内優先
        _fA = sorted([t for t in _fout_all if bo[t['w']-1]['級別'] in ('A1','A2')], key=lambda x: x['w'])
        _fB = sorted([t for t in _fout_all if bo[t['w']-1]['級別'] not in ('A1','A2')], key=lambda x: x['w'])
        # カドF単独（F艇がカドで5のみ/6のみ＝他にF艇なし）は除外＝f_outを空にしてD3等へ流す
        # 実測(programs全期間)：5号艇F単独34.6%/6号艇F単独23.1%と4号艇F42%台より明確に低い弱層
        if len(_fout_all) == 1 and _fout_all[0]['w'] in (5, 6):
            f_out = []
        else:
            f_out = _fA + _fB
        f_in  = [b for b in bo if int(b['枠']) in (2,3) and int(b['F数']) >= 1]
        o4top = o4[0] if o4 else None
        # 場の①着外率（実測・分母つき）。死角の文で「どれくらい起きるか」を数字で示すために使う。
        _cpv = _collapse.get(bo[0]['場コード']) or {}
        _cp_rate = (f"{_cpv.get('inOutRate')}%（{_cpv.get('n')}レース）"
                    if _cpv.get('inOutRate') is not None else "実数を出せていない")
        o4kt = kim_type(toban_by_w.get(o4top['w'], '')) if o4top else None
        if f_out:
            t = f_out[0]
            saten = f"{K[t['w']-1]}{nm(bo[t['w']-1]['氏名'])}はF{bo[t['w']-1]['F数']}本。{K[t['w']-1]}が慎重に構えるなら、①の残り目も。"
            skw = t['w']; sid = 'D1'
        elif f_in:
            fw = int(f_in[0]['枠'])
            saten = f"{K[fw-1]}{nm(bo[fw-1]['氏名'])}はF{bo[fw-1]['F数']}本。{K[fw-1]}が慎重に構えるなら、①の残り目も。"
            skw = fw; sid = 'D2'
        elif in_strong:
            saten = f"①{nm(in1['氏名'])}が先マイを決めれば、そのまま押し切る形。"
            skw = 1; sid = 'D3'
        elif any(t['mhi'] for t in threats if t['w'] < 4):
            mb = next(t for t in threats if t['w'] < 4 and t['mhi'])
            saten = f"{K[mb['w']-1]}{nm(bo[mb['w']-1]['氏名'])}はモーター2連率{round(bo[mb['w']-1]['_mtr'])}%（場平均{round(mavg2)}%）。{K[mb['w']-1]}は差し・まくり差しから連に。"
            skw = mb['w']; sid = 'D4'
        elif in_weak:
            # ①不安時の死角を、弱点理由×外主役の決まり手で分岐（同文回避）
            wl = []
            if not inA: wl.append('格')
            if il > 0 and il < ina: wl.append('当地')
            if in_lo: wl.append('機力')
            if o4top and o4kt == 'makuri' and ba in NARROW:
                # 死角艇は実際にまくる外脅威(o4top)に付け替え＝旧⑥ハードコード(絡み30%)は過剰。
                # 実測：D5該当レースで6号艇3着内30.1%に対しo4top(多くは4号)は48.3%。文言も弱化。
                saten = f"{K[o4top['w']-1]}{nm(bo[o4top['w']-1]['氏名'])}のまくりが決まれば、内の隊形は乱れる。"
                skw = o4top['w']; sid = 'D5'
            elif o4top and o4kt == 'makuri':
                saten = f"{K[o4top['w']-1]}{nm(bo[o4top['w']-1]['氏名'])}のまくりが決まれば、内の粘りごと連れ去る形。"
                skw = o4top['w']; sid = 'D6'
            elif o4top and o4kt == 'sashi':
                saten = f"{K[o4top['w']-1]}{nm(bo[o4top['w']-1]['氏名'])}の差しが甘くなれば、①{nm(in1['氏名'])}の粘り込みも。"
                skw = 1; sid = 'D7'
            elif in_lo:
                saten = f"①{nm(in1['氏名'])}のモーター2連率は{round(mt[0])}%（場平均{round(mavg2)}%）。①の伸びが戻れば、逃げ残りも。"
                skw = 1; sid = 'D8'
            elif '格' in wl and '当地' not in wl:
                saten = f"①{nm(in1['氏名'])}は当地{il:.2f}で全国{ina:.2f}を上回る。①のSが五分なら、押し切る目も。"
                skw = 1; sid = 'D9'
            elif '当地' in wl:
                saten = f"①{nm(in1['氏名'])}は当地{il:.2f}。①が水面に慣れていれば、連の一角に残る目も。"
                skw = 1; sid = 'D10'
            else:
                saten = f"①{nm(in1['氏名'])}のSが五分なら、外の攻めは届きにくい。①の残り目も。"
                skw = 1; sid = 'D11'
        elif any(t['w'] >= 4 for t in threats):
            # 外の仕掛けを担う筆頭＝threatsのw>=4で最内の艇（実測：D12死角艇は内ほど絡む
            # 4号57.8%>5号42.9%>6号29.3%。最外選択は6号偏重で弱いため最内優先に変更）
            out_thr = sorted([t for t in threats if t['w'] >= 4], key=lambda x: x['w'])
            saten = f"{K[out_thr[0]['w']-1]}{nm(bo[out_thr[0]['w']-1]['氏名'])}が仕掛ければ、隊形は乱れる。"
            skw = out_thr[0]['w']; sid = 'D12'
        else:
            # 内が壁を作る＝主役の①が残る想定。死角艇は①
            saten = f"②③が壁を作れば、隊形は内で収まる。"
            skw = 1; sid = 'D13'
        tenkai.append(saten)

        # ①が崩れる時の「崩れ方」場別分布（当場・過去1年の実数。①着外レースの内訳）。※波及IDの分岐でも参照。
        #   確率/買い目/予想ではない。母数不足(patterns=null)の場は top=null。追加のみ・スコア非関与。
        _cp = _collapse.get(bo[0]['場コード'])
        if _cp:
            _cp_pats = _cp.get('patterns')
            collapse = {
                'top': (_cp_pats[0] if _cp_pats else None),
                'patterns': (_cp_pats[:3] if _cp_pats else None),  # 表示用 上位3（母数不足はnull）
                'n': _cp.get('n'),
                'inOutRate': _cp.get('inOutRate'),
                'kimariteSum': _cp.get('kimariteSum') or {}
            }
            # B案：最多パターン(top)の艇について、今日の“勝ち方の内訳”を事実併記する（実数のみ・因果は主張しない）。
            # まくり率＝まくり1着数÷1着数で「勝ち方の内訳」であり「仕掛ける頻度」ではない。誤解回避のため
            #   ①母数ガード：1着数<10 は併記しない ②分母(1着数)を必ず見せる（「{勝}勝中{該当}勝が{手}」）。
            _tv = None
            _tp = collapse['top']
            if _tp and _tp.get('boat') and 1 <= _tp['boat'] <= len(bo):
                _tk = _tp.get('kimarite') or ''
                _ty = yarare.get(bo[_tp['boat'] - 1]['登録番号']) or {}
                _wins = _ty.get('1着数')
                if 'まくり' in _tk:
                    _num, _lbl = _ty.get('まくり数'), 'まくり'
                elif '差し' in _tk:
                    _num, _lbl = _ty.get('差し数'), '差し'
                else:
                    _num, _lbl = None, None
                # 1着数10以上（＝勝ち方の傾向が言える程度に勝っている）かつ該当数が取れる場合のみ併記
                if _wins is not None and _wins >= 10 and _num is not None:
                    _tv = {'boat': _tp['boat'], 'kimarite': _lbl, 'wins': _wins, 'num': _num}
            collapse['todayRival'] = _tv
        else:
            collapse = None

        # --- 波及の連鎖（主役の決まり手型×場×イン強弱で分岐。同文を散らす）---
        out4 = any(t['w'] >= 4 for t in threats)
        kt_h = _kt_of(head_w) if (head_w and head_w >= 4) else None
        n1 = nm(in1['氏名']); n2b = nm(bo[1]['氏名'])
        if in_strong and it >= 60:
            suji = f"①{n1}が先マイを決めれば、②③が続く形。{ba}で①が3着以内を外したのは{_cp_rate}。"; fid = 'S1'
        elif in_strong or (not in_weak and not out4):
            suji = f"①{n1}が先マイを決めれば、②③が続く形。{ba}で①が3着以内を外したのは{_cp_rate}。"; fid = 'S2'
        elif out4 and kt_h == 'makuri' and ba in NARROW:
            suji = f"{K[head_w-1]}{boat_meta[head_w]['nm']}が握って回れば、空いた内を⑤⑥が拾う形。{ba}で①が3着以内を外したのは{_cp_rate}。"; fid = 'S3'
        elif out4 and kt_h == 'sashi':
            suji = f"{K[head_w-1]}{boat_meta[head_w]['nm']}がまくり差しに構えれば、①②の間が割れる形。{ba}で①が3着以内を外したのは{_cp_rate}。"; fid = 'S4'
        elif out4 and head_w and head_w >= 4:
            # ①が崩れる構図を実数根拠つきで分岐（S10/S8/S9で S5 の独占を解消）。
            # 場タイプは collapsePattern の kimariteSum(まくり+まくり差し / 差し)から動的判定（閾値ハードコードなし）。
            _ks = (collapse or {}).get('kimariteSum') or {}
            _mak = round(_ks.get('まくり', 0) + _ks.get('まくり差し', 0), 1)  # まくり系
            _sas = _ks.get('差し', 0)
            _cn = (collapse or {}).get('n')
            _ctop = (collapse or {}).get('top') or {}
            if downFactors['count'] == 0:
                suji = f"①{n1}に下振れの材料は出ていない。{ba}で①が3着以内を外したのは{_cp_rate}。"; fid = 'S10'
            elif collapse and _mak >= 72 and _ctop.get('boat'):
                suji = f"{ba}で①が着外に沈んだ{_cn}レースのうち、{_mak}%がまくり決着。差しは{_sas}%。最多は{_ctop['boat']}号艇。"; fid = 'S8'
            elif collapse and _sas >= 22:
                # 差しパターンは full patterns(上位5)から拾う（表示用top3にはまくりしか無い場があるため）。
                _sp = next((p for p in ((_cp or {}).get('patterns') or []) if p.get('kimarite') == '差し'), None)
                _spt = f"{_sp['boat']}号艇の差し{_sp['pct']}%" if _sp else "内の差し"
                suji = f"{ba}で①が着外に沈んだ{_cn}レースのうち、差しが{_sas}%。最多は{_spt}。"; fid = 'S9'
            else:
                suji = f"{K[head_w-1]}{boat_meta[head_w]['nm']}が仕掛ければ、②③は外に張られる形。{ba}で①が3着以内を外したのは{_cp_rate}。"; fid = 'S5'
        elif out4:
            ow = o4[0]['w'] if o4 else 4
            suji = f"{K[ow-1]}{boat_meta[ow]['nm']}が仕掛ければ、②③は外に張られる形。{ba}で①が3着以内を外したのは{_cp_rate}。"; fid = 'S6'
        else:
            suji = f"②{n2b}が差し込めば、①{n1}は2着に残る形。{ba}で①が3着以内を外したのは{_cp_rate}。"; fid = 'S7'

        # --- 今節の展示（前日まで）。6艇平均との差が 0.05 秒以上ついた艇だけ、締めの前に1行置く。
        #     0.05 未満は「ほぼ平均」にしかならず読者の判断が変わらないため出さない（深層には全艇を出す）。
        #     対象は①と対抗の2艇。本数は必ず併記する。
        _tj_line = None
        _tj_cand = [(1, in1)]
        if head_w and 1 <= head_w <= 6:
            _tj_cand.append((head_w, bo[head_w - 1]))
        _tj_hit = []
        for _w, _b in _tj_cand:
            _dv, _nn = tenji_dev(_b, bo[0].get('開催日', ''))
            if _dv is not None and abs(_dv) >= 0.05:
                _tj_hit.append(f"{K[_w-1]}{nm(_b['氏名'])}は今節の展示が6艇平均より"
                               f"{abs(_dv):.2f}秒{'速い' if _dv < 0 else '遅い'}（{_nn}本）")
        if _tj_hit:
            tenkai.append('。'.join(_tj_hit) + '。')

        # --- 締めの1行：展示で何を見るかを艇番で名指しする（定型の言い回しをやめた）---
        _shw = (f"{K[head_w-1]}{boat_meta[head_w]['nm']}" if head_w and head_w in boat_meta
                else (f"{K[threats[0]['w']-1]}{threats[0]['nm']}" if threats else '外'))
        if verdict == '堅め':
            if diff >= 0.30 and in_strong:
                shime = f"展示では、①{nm(in1['氏名'])}の直線と{_shw}の行き足を見たい。"; cid = 'C1'
            elif in_strong:
                shime = f"展示では、{_shw}のSと行き足を見たい。"; cid = 'C2'
            else:
                # 数字は①寄りだが文面は主役を絞れていない：矛盾しない締めに落とす
                shime = f"展示では、①{nm(in1['氏名'])}の直線を見たい。"; cid = 'C6'
        elif verdict == '波乱':
            tgt = K[head_w-1] if head_w else '外'
            if in_weak:
                shime = f"展示では、{_shw}のSと①{nm(in1['氏名'])}の直線を見たい。"; cid = 'C3'
            else:
                shime = f"展示では、{_shw}の行き足を見たい。"; cid = 'C7'
        else:
            if hero == 4:
                shime = f"展示では、進入と{_shw}の行き足を見たい。"; cid = 'C4'
            else:
                shime = f"展示では、{_shw}のSを見たい。"; cid = 'C5'
        tenkai.append(shime)

        # --- 検証ログ（拡張）：対抗・死角・文パターンIDまで保存し、書き方自体を検証可能に ---
        pred_entry = {'場名': ba, '場コード': bo[0]['場コード'], 'レース': rc,
                          '判定': verdict, '主役艇': hero, 'スコア': diff,
                          '対抗艇': (th2[1]['w'] if len(th2) > 1 else None),
                          '死角艇': skw,
                          '見出しID': hid, '死角ID': sid, '波及ID': fid, '締めID': cid,
                          'スコア内訳': score_breakdown}

        boats = []
        for b in bo:
            w = int(b['枠']); loc = f(b['当地勝率']); nat = f(b['全国勝率']); st = f(b['平均ST']); mv = b['_mtr']
            _mno = (b.get('モーターNo') or '').strip() or None
            _m2 = f(b.get('モーター2連率'))
            _runs = motor_runs(b.get('モーター2連率'), b.get('モーター3連率'))
            # 2連率0%でも3連率が付いていれば「走っているが不振」。未走（新替直後）と区別する。
            _ran = (_m2 > 0) or f(b.get('モーター3連率')) > 0
            mev = 'na'
            if _ran and mavg2 and (_runs is None or _runs >= MOTOR_MIN_RUNS):
                mev = 'hi' if _m2 > mavg2 + 5 else 'lo' if _m2 < mavg2 - 5 else 'mid'
            y = yarare.get(b['登録番号'], {})
            # 誕生日マーク: この艇の開催日がその選手の誕生日のときだけキーを足す。
            # 全艇に null を持たせると highlights.json が無駄に太るため該当者のみ。
            # 判定は scripts/birthdayMark.py（2月29日生まれは平年2月28日で成立）。
            _bdm = birthdayMark.mark_on(
                BIRTH_MAP.get(b['登録番号']),
                birthdayMark.ymd8_to_date(b.get('開催日') or ''))
            _boat = {
                '枠': w, '登録番号': b['登録番号'], '支部': b.get('支部',''), '級別': b['級別'], '氏名': nm(b['氏名']),
                '全国勝率': round(nat, 2), '当地勝率': round(loc, 2),
                '機番': _mno, '走破数': _runs,
                '機力': round(_m2, 1) if _m2 > 0 else None, '機力評価': mev,
                'F': int(b['F数']) >= 1, '鋭ST': st > 0 and st <= 0.15,
                '当地優位': loc > 0 and loc > nat,
                'さされ率': y.get('さされ率'), 'まくられ率': y.get('まくられ率'),
                'まくりさされ率': y.get('まくりさされ率'), 'イン数': y.get('イン数'),
                'まくり率': y.get('まくり率'), '差し率': y.get('差し率'),  # 追加:B案の事実併記用(null許容)
                '1着数': y.get('1着数'), 'まくり数': y.get('まくり数'), '差し数': y.get('差し数'),  # 追加:母数/分母(null許容)
                'inWinRate': (_inrate.get(b['登録番号']) or {}).get('rate'),  # 追加:①1着率(null許容)
                # 今節の展示タイム偏差（6艇平均との差・本数）。深層の一覧で6艇ぶん出す。
                # 生の秒数は出さない。2本未満は偏差を出さず本数だけ返る。
                '今節展示': (lambda _d, _n: {'偏差': _d, '本数': _n})(*tenji_dev(b, bo[0].get('開催日', ''))),
                # 今節の走り（前日まで）。着順・ST・進入コースの時系列。深層の一覧で使う。
                '今節の走り': setsu_trail(b)
            }
            if _bdm:
                _boat['誕生日'] = {'歳': _bdm[0]}
                if _bdm[1]:
                    _boat['誕生日']['注記'] = _bdm[1]
            boats.append(_boat)

        out_entry = {
            '場名': ba, '場コード': bo[0]['場コード'], 'レース': rc,
            '締切時刻': bo[0].get('締切時刻', ''),
            '節名': bo[0].get('節名', ''), '企画名': bo[0].get('企画名', ''),
            '日目': bo[0].get('日目', ''),
            '波乱': seeds, 'イン堅': in_strong, 'モーター使用': use_m, 'イン1着率': it,
            # 深層の下振れ要因ブロックで、①の機力の比較対象として使う（単独の数字を置かないため）。
            'モーター場平均': round(mavg2, 1) if mavg2 else None,
            '艇': boats, '見立て': headline, '展開': tenkai, '波及': suji,
            'downFactors': downFactors,  # 追加:①の下振れ要因（事実提示・確率/買い目なし）
            'collapse': collapse  # 追加:①の崩れ方（場別実数・確率/買い目なし。①着外レースの内訳）
        }
        return out_entry, pred_entry

    # 呼び出し：場×レース単位に例外を握って「取れた分だけ」蓄積。失敗はログ。
    failed = []
    for (ba, rc), bo in races.items():
        try:
            _res = _one(ba, rc, bo)
        except Exception as e:
            failed.append((ba, rc, repr(e)))
            continue
        if _res is None:
            continue
        _out, _pred = _res
        out_races.append(_out)
        pred_list.append(_pred)
    if failed:
        vs = sorted(set(ba for ba, _rc, _e in failed))
        print("部分成功: {}レースをスキップ（例外を握って継続）／該当場: {}".format(len(failed), '・'.join(vs)))
        for ba, rc, err in failed[:50]:
            print("  SKIP {} {} : {}".format(ba, rc, err))

    kaisai = rac[0]['開催日'] if rac else ''

    # ---- モーター新替の検出・記録 ----
    # 節初日に場の全行がモーター2連率 0 かつボート2連率 0 なら、実績のない新品と見なす。
    # 個別の 0% は「未走」と「走ったが連対なし」を区別できないので、場単位の全滞のみ採用する。
    motor_replace = {}
    try:
        with open(MOTOR_REPLACE, encoding='utf-8') as _rf:
            motor_replace = json.load(_rf) or {}
    except Exception:
        motor_replace = {}
    _by_venue = defaultdict(list)
    for _r in rac:
        _by_venue[_r['場コード']].append(_r)
    _repl_changed = False
    for _ba, _rs in _by_venue.items():
        if not _rs or _rs[0].get('日目') != '初日':
            continue
        if any(f(_x.get('モーター2連率')) != 0 for _x in _rs):
            continue
        if any(f(_x.get('ボート2連率')) != 0 for _x in _rs):
            continue
        _hd = _rs[0].get('開催日', '')
        if not _hd or (motor_replace.get(_ba) or {}).get('新替日') == _hd:
            continue
        motor_replace[_ba] = {'新替日': _hd, '節名': _rs[0].get('節名', ''), '記録': 'auto'}
        _repl_changed = True
        print('motorReplace detected: {} {}'.format(_ba, _hd))
    if _repl_changed:
        os.makedirs(os.path.dirname(MOTOR_REPLACE) or '.', exist_ok=True)
        with open(MOTOR_REPLACE, 'w', encoding='utf-8') as _wf:
            json.dump(motor_replace, _wf, ensure_ascii=False, indent=1, sort_keys=True)
            _wf.write('\n')

    doc = {
        '生成時刻': datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(timespec='seconds'),
        '開催日': kaisai,
        '確定イン率場': sorted(CONFIRMED),
        'モーター新替': motor_replace,
        # 深層で「単独の数字を置かない」ための比較基準。表層には出さず、タップした先でだけ使う。
        '1コース1着率の基準': {
            '中央値': _med_rate, '人数': _n_rate, '最低走数': 20,
            '集計日': _inrate_updated, '出典': 'データ攻め（YouTube あべけん）'
        },
        'レース数': len(out_races),
        'レース': out_races
    }
    # ---- 自己検査(生成前) ----
    # 出走表が空 / 0レース＝生成失敗。既存 highlights・predictions を壊さず非ゼロ終了する
    # （上書きゼロ・鉄則厳守）。夜間の翌日分プレビュー(kaisai!=today)は下の日付ガードで正当スキップ。
    n_races = len(out_races)
    n_venues = len(set(r.get('場コード') for r in out_races))
    if not rac or n_races == 0:
        print("SELFCHECK NG: 出走表{}行 / 生成{}レース ＝ 生成失敗。"
              "既存 highlights・predictions は保持（上書きせず）".format(len(rac), n_races))
        sys.exit(3)

    # --- 翌日モード: highlights_next.json へ場単位マージ（当日 highlights.json・predictions/ は触らない）---
    if NEXT:
        now_iso = doc['生成時刻']
        now_hm = now_iso[11:16]
        by_jcd = defaultdict(list)
        for r in out_races:
            by_jcd[r.get('場コード')].append(r)
        run_meta = {}
        for jcd, rs in by_jcd.items():
            nR = len(rs)
            run_meta[jcd] = {'場名': rs[0].get('場名', ''), 'generatedAt': now_hm,
                             'partial': nR < FULL_RACES, 'レース数': nR}
        # 既存 next を読み、同一対象日ならマージ（このrunに無い＝未到着の場は据え置き）。別日なら破棄。
        merged_races, merged_meta = [], {}
        try:
            with open(NEXT_OUT, encoding='utf-8') as nf:
                oldn = json.load(nf)
            if (oldn.get('開催日') or '') == kaisai:
                keep = set(by_jcd.keys())
                merged_races = [r for r in (oldn.get('レース') or []) if r.get('場コード') not in keep]
                merged_meta = {k: v for k, v in (oldn.get('場別') or {}).items() if k not in keep}
        except Exception:
            pass
        merged_races.extend(out_races)   # このrunの場は最新で上書き（載せてから更新）
        merged_meta.update(run_meta)
        next_doc = {
            '生成時刻': now_iso, '開催日': kaisai, 'プレビュー': True,
            '確定イン率場': sorted(CONFIRMED),
            'モーター新替': motor_replace,
            'レース数': len(merged_races), 'レース': merged_races,
            '場別': merged_meta,
        }
        os.makedirs(os.path.dirname(NEXT_OUT) or '.', exist_ok=True)
        with open(NEXT_OUT, 'w', encoding='utf-8') as nf:
            json.dump(next_doc, nf, ensure_ascii=False, separators=(',', ':'))
        part = sum(1 for m in merged_meta.values() if m.get('partial'))
        print("OK(翌日): 対象{} 今回{}場/{}レース → next計{}場/{}レース(一部公開{}場) → {}".format(
            kaisai, len(by_jcd), len(out_races), len(merged_meta), len(merged_races), part, NEXT_OUT))
        # 鉄則: predictions/ には一切書かない。prevローテーションもしない。当日 highlights.json も不変。
        return

    # 壁時計（JST）が今日になっている開催日のときだけ当日を書き換える。
    # 出走表が夜に翌日分へ更新されても、当日タブを前倒しで繰り上げない。
    today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime('%Y%m%d')
    if kaisai != today:
        print(f"SKIP: 開催日{kaisai} != 本日{today}（当日を保持）")
        return
    out_dir = os.path.dirname(OUT)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    prev_path = os.path.join(out_dir, 'highlights_prev.json') if out_dir else 'highlights_prev.json'
    prev2_path = os.path.join(out_dir, 'highlights_prev2.json') if out_dir else 'highlights_prev2.json'
    try:
        with open(OUT, 'r', encoding='utf-8') as pf:
            old_doc = json.load(pf)
        if old_doc.get('開催日') and old_doc.get('開催日') != kaisai:
            if os.path.exists(prev_path):
                os.replace(prev_path, prev2_path)
            with open(prev_path, 'w', encoding='utf-8') as pf:
                json.dump(old_doc, pf, ensure_ascii=False, separators=(',', ':'))
    except FileNotFoundError:
        pass
    except Exception:
        pass
    with open(OUT, 'w', encoding='utf-8') as fp:
        json.dump(doc, fp, ensure_ascii=False, separators=(',', ':'))
    print(f"OK: {n_races}レース/{n_venues}場 → {OUT}")

    # 見どころ4タブ分の選手成績JSON。highlights.json と prev ローテーションを終えた後に
    # 出す付随生成物なので、ここで失敗しても既存の生成物は壊さず処理を続ける
    # （見どころ本体を巻き込まない）。
    try:
        write_racer_stats_today(doc['生成時刻'])
    except Exception as e:
        print(f"NOTE: {STATS_OUT} の生成に失敗（highlights.json は正常）: {e}")

    # --- 検証ログ：予測を確定保存（結果を見る前・一度書いたら動かさない）---
    # 公開highlights.jsonには判定/主役艇を入れず、非公開predictions/にだけ残す。
    pred_written = None
    if pred_list:
        os.makedirs('predictions', exist_ok=True)
        pred_path = os.path.join('predictions', f'{kaisai}.json')
        if os.path.exists(pred_path):
            print(f"PRED skip: {pred_path} 既存（予測は動かさない）")
        else:
            pred_doc = {'開催日': kaisai, '生成時刻': doc['生成時刻'],
                        '閾値': {'堅め': TH_KATA, '波乱': TH_HARAN},
                        '予測': pred_list}
            with open(pred_path, 'w', encoding='utf-8') as pf:
                json.dump(pred_doc, pf, ensure_ascii=False, separators=(',', ':'))
            pred_written = pred_path
            print(f"PRED: {len(pred_list)}レース → {pred_path}")

    # ---- 自己検査(生成後) ----
    # 書いたファイルを読み直し、JSONとして開けて中身が空でないことを確認。
    # 破損/空なら非ゼロ終了して以降(コミット等)を止める。既存predictionsは検査対象外(不変)。
    try:
        with open(OUT, encoding='utf-8') as _cf:
            _c = json.load(_cf)
        if not (_c.get('レース数', 0) > 0 and _c.get('レース')):
            raise ValueError("highlights.json のレースが空")
    except Exception as e:
        print(f"SELFCHECK NG(生成後): highlights.json 再読込検査に失敗: {e}")
        sys.exit(4)
    if pred_written:
        try:
            with open(pred_written, encoding='utf-8') as _pf:
                _p = json.load(_pf)
            if not _p.get('予測'):
                raise ValueError("predictions の予測が空")
        except Exception as e:
            print(f"SELFCHECK NG(生成後): {pred_written} 再読込検査に失敗: {e}")
            sys.exit(4)
    print("SELFCHECK OK: highlights {}レース/{}場, predictions {}".format(
        n_races, n_venues,
        f"{len(pred_list)}レース(新規)" if pred_written else "既存保持/対象なし"))

if __name__ == '__main__':
    main()
