# -*- coding: utf-8 -*-
# buildResults.py
# boatraceopenapi/api(GitHub Pages配信)から全24場・全レースの
# 着順(組番)・決まり手・全式別払戻を抽出し results/YYYYMMDD.json に出力。
# 見立て検証(verifyPredictions.py)の結果側データ、および結果表ページ(docs/results/)の元データ。
#
# 取得元: https://raw.githubusercontent.com/boatraceopenapi/api/gh-pages/docs/v1/YYYY/YYYYMMDD.json
#   ・旧取得元 BoatraceOpenAPI/results v2 は非推奨宣言済み。後継の boatraceopenapi/api v1 へ移行。
#     v1は約3分間隔で更新され、当日分もレース確定ごとに追記される。対応期間は2026-01-01以降。
#   ・2025-07-15〜2025-12-31 の results/*.json は v1 に存在しない期間のため、既存ファイルを残置する。
#     本スクリプトは指定日ぶんのみを書き出し、既存の他日ファイルには触れない。
#   ・GitHub配信のためGitHub ActionsのIPからも通る(mbraceのIPブロック問題を回避)。
#   ・当日結果はレース確定後に反映。未確定/非開催日は404。
#   ・v1には決まり手(technique_number)と全式別払戻(trifecta/trio/exacta/
#     quinella/quinella_place/win/place)が含まれるため mbrace LZH は不要。
#   ・レース単位の実測条件(風速/風向/波高/天候/気温/水温)も含まれる。これらは
#     weather.json(Open-Meteoの予報値)と違い、レース時点の実測値。現時点で用途は
#     決めていないが、過去に遡れる保証がないため取得できるものは全項目保存する。
#     風向・天候はAPIがコード値で返す。変換は表示側の役割とし、ここでは生値のまま持つ。
#   ・v1のpayoutsは配当額のキーが amount(v2は payout)。出力形式は従来どおり。
#   ・級別(rank_number_source="A1"等 / rank_number=1〜4)は番組表側(レース直下のracers)にある。
#     結果側(result.racers)には無いので、枠番(entry_number)で突き合わせて取る。これは
#     レース当時の級別なので、期首固定の現在値(docs/data/racerStatsCore.json)と違い
#     過去のレースにも当時の事実が出る。生値とコードの両方を保存する。
#     2025-07-15〜2025-12-31 の既存ファイルは旧取得元(v2)由来で rank 系を持たないため、
#     この期間の級別は入らない(取れなかったものは埋めない)。
#
# 本番: 環境変数なしで当日(JST)分を取得。
# 複数日: 環境変数 HD にカンマ区切りで日付(YYYYMMDD)を渡すと全日ぶん取得(過去分の穴埋め用)。
#
# 欠けレースの補完(2026-10-28 追加):
#   v1 はレース枠(result)を持っていても中身が空(着順・払戻すべて null/空)のまま
#   当日中ずっと埋まらないことがある。2026-10-27 は v1 の最終版(11:56 UTC)で
#   13レースが空(デイ6場の12R・福岡11R・ナイター場の2〜3R等)で、v1 の更新は
#   その後止まり、翌日まで埋まらなかった。一方、旧取得元 v2 は数時間おきの一括更新で
#   同日 09:45 UTC 版にデイ場の全レースを持っていた。
#   そこで v1 で3連単が取れないレースだけ v2 から補う。v1 にあるレースは v1 を優先し、
#   v2 で上書きしない。v2 が取れない(404・廃止)ときは従来どおり v1 だけで書く。
#   級別は v2 に無いので、補ったレースも v1 の番組表側から枠番で引く。
#
# 公式サイトからの第2の予備(2026-10-29 追加):
#   v1・v2 とも更新が数時間止まることがある(2026-10-28 22:42 JST に v1 で26レースが空、
#   v2 でも1レースしか補えなかった)。そこで v1 で欠け、v2 でも補えなかったレースだけ、
#   公式の結果ページ(boatrace.jp raceresult)を1レースずつ読んで補う。
#   ・対象は「v1 の結果側に着順が1つも無い」かつ「締切(closed_at)から10分以上たった」レース。
#     v1 に着順があるのに3連単が無いレースは 3連単不成立(例: 2026-10-28 桐生12R)なので取りに行かない。
#   ・3連単の組番と配当が読めないページ(未確定・レース中止・データなし)は補わない。
#   ・1リクエストごとに1秒以上あける。1日あたり最大 OFFICIAL_MAX 件。失敗は黙って飛ばす。
#   ・GitHub Actions からは届く(scrapeLiveWeather.py の beforeinfo と同じ作法)。
#     届かない環境(プロキシで403等)では何も補わず、従来どおり v1・v2 だけで書く。
#   ・ページの値は v1 の _source 系と同じ表記(着の「転」「F」等、ST の「F.01」)なので、
#     コードへの直し方も v1 に合わせる(着 7=妨〜16=欠、F の ST は負の値)。
import io
import os
import re
import ssl
import html as htmllib
import json
import time
import datetime
import unicodedata
import urllib.request

BASE = "https://raw.githubusercontent.com/boatraceopenapi/api/gh-pages/docs/v1/"
BASE_V2 = "https://raw.githubusercontent.com/BoatraceOpenAPI/results/HEAD/docs/v2/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) boatrace-data-collector"
OFFICIAL_URL = "https://www.boatrace.jp/owpc/pc/race/raceresult?rno={rno}&jcd={jcd:02d}&hd={hd}"
OFFICIAL_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
OFFICIAL_SLEEP = 1.2
OFFICIAL_MAX = int(os.environ.get("OFFICIAL_MAX", "60"))
OFFICIAL_AFTER_MIN = 10   # 締切からこの分数がたったレースだけ取りに行く

# 公式ページの着の表記 → v1 の place_number(facts.md の着コード表と同じ)
PLACE_CODE = {"妨": 7, "エ": 8, "転": 9, "落": 10, "沈": 11, "不": 12,
              "失": 13, "F": 14, "L": 15, "欠": 16}
# 公式ページの勝式 → v1 の payouts キー
BET_KEY = {"3連単": "trifecta", "3連複": "trio", "2連単": "exacta", "2連複": "quinella",
           "拡連複": "quinella_place", "単勝": "win", "複勝": "place"}

# 決まり手コード(technique_number) → 表記
TECHNIQUE = {
    1: "逃げ", 2: "差し", 3: "まくり",
    4: "まくり差し", 5: "抜き", 6: "恵まれ",
}


def _payouts(payouts):
    """OpenAPIのpayoutsを、式別ごとの[{組番,配当}...]に整形して返す。
    単勝/複勝/2連単/2連複/拡連複/3連複/3連単の順。配当欠損は0/Noneを除外。"""
    # OpenAPIキー → 日本語式別名
    mapping = [
        ("win", "単勝"),
        ("place", "複勝"),
        ("exacta", "2連単"),
        ("quinella", "2連複"),
        ("quinella_place", "拡連複"),
        ("trio", "3連複"),
        ("trifecta", "3連単"),
    ]
    out = {}
    for key, label in mapping:
        rows = []
        for e in payouts.get(key, []) or []:
            combo = e.get("combination")
            pay = e.get("amount")
            if not combo or pay in (None, 0):
                continue
            try:
                rows.append({"組番": combo, "配当": int(pay)})
            except Exception:
                continue
        out[label] = rows
    return out


def fetch_json(hd, base=BASE):
    """指定日(YYYYMMDD)の結果JSONを取得してdictで返す。404/失敗はNone。"""
    y = hd[:4]
    url = "{0}{1}/{2}.json".format(base, y, hd)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read()
    except Exception:
        return None
    if not raw or len(raw) < 20:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None


def _has_trifecta(res):
    """resultに3連単の組番と配当があるか(=確定結果として使えるか)。"""
    tri = ((res or {}).get("payouts") or {}).get("trifecta") or []
    return bool(tri) and bool(tri[0].get("combination")) and tri[0].get("amount") not in (None, 0)


def v2_results(data2):
    """旧取得元v2の結果を、v1のresultと同じ形に直して {(場番号,R番号): result} で返す。
    v2はキー名が違うだけで値は同じ(2026-10-27分の重複レースで全項目一致を確認)。"""
    out = {}
    for r in (data2 or {}).get("results") or []:
        try:
            key = (int(r["race_stadium_number"]), int(r["race_number"]))
        except Exception:
            continue
        racers = {}
        for b in r.get("boats") or []:
            en = b.get("racer_boat_number")
            if en is None:
                continue
            racers[str(en)] = {
                "entry_number": en,
                "course_number": b.get("racer_course_number"),
                "start_timing": b.get("racer_start_timing"),
                "place_number": b.get("racer_place_number"),
                "number": b.get("racer_number"),
                "name": b.get("racer_name"),
            }
        payouts = {}
        for k, rows in (r.get("payouts") or {}).items():
            payouts[k] = [{"combination": e.get("combination"), "amount": e.get("payout")}
                          for e in (rows or []) if isinstance(e, dict)]
        out[key] = {
            "date": r.get("race_date"),
            "stadium_number": key[0],
            "race_number": key[1],
            "wind_speed": r.get("race_wind"),
            "wind_direction_number": r.get("race_wind_direction_number"),
            "wave_height": r.get("race_wave"),
            "weather_number": r.get("race_weather_number"),
            "air_temperature": r.get("race_temperature"),
            "water_temperature": r.get("race_water_temperature"),
            "technique_number": r.get("race_technique_number"),
            "racers": racers,
            "payouts": payouts,
        }
    return out


def _text(s):
    """タグを除き、実体参照を戻し、全角英数をNFKCで半角にして空白を1つに詰める。"""
    s = htmllib.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    s = unicodedata.normalize("NFKC", s)
    return re.sub(r"\s+", " ", s).strip()


def _num(s):
    """'9.0℃' '9m' '8cm' → 数値。整数なら int(v1 と同じ)。読めなければ None。"""
    m = re.search(r"-?\d+(?:\.\d+)?", s or "")
    if not m:
        return None
    v = float(m.group(0))
    return int(v) if v.is_integer() else v


def _section(h, head):
    """<th>head</th> から次の </table> までの HTML。無ければ空文字。"""
    i = h.find("<th>%s</th>" % head)
    if i < 0:
        return ""
    j = h.find("</table>", i)
    return h[i:j if j > 0 else len(h)]


def _st(src):
    """'.18' → 0.18、'F.01' → -0.01(v1 と同じ)。それ以外(L・空)は None。"""
    m = re.match(r"^(F)?\s*(\d*\.\d+)$", src or "")
    if not m:
        return None
    v = float(m.group(2))
    return -v if m.group(1) else v


def parse_official(page, hd, jcd, rno):
    """公式 raceresult ページの HTML を、v1 の result と同じ形の dict にして返す。
    3連単の組番と配当が読めないとき(未確定・レース中止・不成立・データなし)は None。"""
    if not page or "<th>勝式</th>" not in page:
        return None
    # 払戻
    payouts = {}
    for body in _section(page, "勝式").split("<tbody")[1:]:
        lab = re.search(r'<td rowspan="\d+">\s*([^<]+?)\s*</td>', body)
        key = BET_KEY.get(_text(lab.group(1))) if lab else None
        if not key:
            continue
        rows = []
        for tr in body.split("<tr")[1:]:
            parts = re.findall(r'class="numberSet1_(?:number|text)[^"]*"[^>]*>([^<]*)<', tr)
            combo = "".join(_text(p) for p in parts)
            am = re.search(r'class="is-payout1">\s*&yen;\s*([\d,]+)', tr)
            if not combo or not am:
                continue
            rows.append({"combination": combo, "amount": int(am.group(1).replace(",", "")),
                         "label": None})
        payouts[key] = rows
    tri = payouts.get("trifecta") or []
    if not tri or not re.fullmatch(r"[1-6]-[1-6]-[1-6]", tri[0]["combination"]):
        return None
    # 着順(着・枠・登番・氏名)
    racers = {}
    for body in _section(page, "着").split("<tbody")[1:]:
        tds = re.findall(r"<td[^>]*>(.*?)</td>", body, re.S)
        if len(tds) < 3:
            continue
        place_src = _text(tds[0])
        en = _text(tds[1])
        if not en.isdigit():
            continue
        tou = re.search(r'class="is-fs12">\s*(\d{4})\s*<', tds[2])
        name = re.search(r'class="is-fs18[^"]*">([^<]*)<', tds[2])
        if place_src.isdigit():
            place = int(place_src)
        else:
            place = PLACE_CODE.get(place_src[:1]) if place_src else None
        racers[en] = {
            "entry_number": int(en),
            "course_number": None,
            "start_timing_source": None,
            "start_timing": None,
            "place_number_source": place_src or None,
            "place_number": place,
            "number_source": tou.group(1) if tou else None,
            "number": int(tou.group(1)) if tou else None,
            "name": _text(name.group(1)) if name else None,
        }
    if len(racers) < 3:
        return None
    # スタート情報(上から1コース・2コース…の順。数字は枠番、続く値がST)
    st_sec = _section(page, "スタート情報")
    nums = re.findall(r'class="table1_boatImage1Number[^"]*">\s*(\d)\s*<', st_sec)
    times = re.findall(r'class="table1_boatImage1TimeInner[^"]*">([^<]*)<', st_sec)
    for course, (en, tm) in enumerate(zip(nums, times), start=1):
        r = racers.get(en)
        if not r:
            continue
        src = (_text(tm).split(" ") or [""])[0]
        r["course_number"] = course
        r["start_timing_source"] = src or None
        r["start_timing"] = _st(src)
    # 決まり手
    tech_src = _text(re.sub(r"<th>決まり手</th>", "", _section(page, "決まり手")))
    tech_no = {v: k for k, v in TECHNIQUE.items()}.get(tech_src)

    # 水面気象(ラベルの直後の値。天候・風向はアイコンのクラス番号 = v1 のコード)
    def _wx(label):
        m = re.search(r'weather1_bodyUnitLabelTitle">%s</span>\s*<span class="weather1_bodyUnitLabelData">([^<]*)<' % label, page)
        return _text(m.group(1)) if m else None
    wnum = re.search(r'weather1_bodyUnitImage is-weather(\d+)', page)
    wdir = re.search(r'weather1_bodyUnitImage is-wind(\d+)', page)
    wname = re.search(r'weather1_bodyUnit is-weather">.*?weather1_bodyUnitLabelTitle">([^<]*)<', page, re.S)
    out = {
        "date": "%s-%s-%s" % (hd[:4], hd[4:6], hd[6:8]),
        "stadium_number": int(jcd),
        "race_number": int(rno),
        "wind_speed_source": _wx("風速"),
        "wind_speed": _num(_wx("風速")),
        "wind_direction_number_source": None,   # ページは矢印画像だけで文字が無い
        "wind_direction_number": int(wdir.group(1)) if wdir else None,
        "wave_height_source": _wx("波高"),
        "wave_height": _num(_wx("波高")),
        "weather_number_source": _text(wname.group(1)) if wname else None,
        "weather_number": int(wnum.group(1)) if wnum else None,
        "air_temperature_source": _wx("気温"),
        "air_temperature": _num(_wx("気温")),
        "water_temperature_source": _wx("水温"),
        "water_temperature": _num(_wx("水温")),
        "technique_number_source": tech_src or None,
        "technique_number": tech_no,
        "racers": racers,
        "payouts": payouts,
        "source": "boatrace.jp raceresult",
    }
    return out


def fetch_official(hd, jcd, rno):
    """公式の結果ページを取得して HTML を返す。失敗は None。"""
    url = OFFICIAL_URL.format(hd=hd, jcd=int(jcd), rno=int(rno))
    req = urllib.request.Request(url, headers=OFFICIAL_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15, context=ssl.create_default_context()) as r:
            return r.read().decode("utf-8", "replace")
    except Exception:
        return None


def official_targets(data, miss, now_jst=None, void=None):
    """欠けレースのうち、公式を見に行くもの。v1 に着順が1つも無く、締切から10分以上たったレースだけ。
    void(dict)を渡すと、着順はあるのに3連単が無いレース（不成立）を {(場,R): "不成立"} で書き足す。"""
    now_jst = now_jst or (datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
                          + datetime.timedelta(hours=9))
    stadiums = ((data.get("programs") or {}).get("stadiums") or {})
    out = []
    for sn, rn in miss:
        race = (((stadiums.get(str(sn)) or {}).get("races") or {}).get(str(rn))) or {}
        res = race.get("result") or {}
        if any((b or {}).get("place_number") is not None for b in (res.get("racers") or {}).values()):
            if void is not None:
                void[(sn, rn)] = "不成立"
            continue   # 着順はあるのに3連単が無い = 不成立。公式にも3連単は無い
        try:
            closed = datetime.datetime.strptime(race.get("closed_at") or "", "%Y-%m-%d %H:%M:%S")
        except Exception:
            continue
        if now_jst < closed + datetime.timedelta(minutes=OFFICIAL_AFTER_MIN):
            continue
        out.append((sn, rn))
    return out[:OFFICIAL_MAX]


def official_fallback(data, hd, filled, void=None):
    """v1 で欠け、v2 でも補えなかったレースを公式の結果ページから補う。
    void(dict)を渡すと、結果が出ないことが確定したレース（中止・不成立）を {(場,R): 理由} で書き足す。"""
    miss = [k for k in missing_races(data) if k not in filled]
    targets = official_targets(data, miss, void=void)
    if not targets:
        return {}
    fb = {}
    for i, (sn, rn) in enumerate(targets):
        if i:
            time.sleep(OFFICIAL_SLEEP)
        page = fetch_official(hd, sn, rn)
        res = parse_official(page, hd, sn, rn)
        if res and _has_trifecta(res):
            fb[(sn, rn)] = res
        elif void is not None and page:
            if "レース中止" in page:
                void[(sn, rn)] = "中止"
            elif "不成立" in page:
                void[(sn, rn)] = "不成立"
    print("official fallback:", hd, "missing", len(miss), "tried", len(targets), "filled", len(fb),
          " ".join("%02d-%dR" % k for k in sorted(fb)))
    return fb


def missing_races(data):
    """v1の番組表にあるのに3連単が取れないレースの (場番号,R番号) を返す。"""
    miss = []
    stadiums = ((data.get("programs") or {}).get("stadiums") or {})
    for sn in stadiums:
        for rn in ((stadiums[sn] or {}).get("races") or {}):
            if not _has_trifecta(((stadiums[sn] or {}).get("races") or {}).get(rn, {}).get("result")):
                miss.append((int(sn), int(rn)))
    return sorted(miss)


def to_races(data, fallback=None):
    """後継API(v1)のprograms/stadiums/racesを、既存results形式のレース配列に変換。
    fallback({(場番号,R番号): v1形のresult})があれば、v1で3連単が取れないレースだけそれで補う。"""
    races = []
    fallback = fallback or {}
    stadiums = ((data.get("programs") or {}).get("stadiums") or {})
    for sn in sorted(stadiums, key=lambda x: int(x)):
        rmap = (stadiums[sn] or {}).get("races") or {}
        for rn in sorted(rmap, key=lambda x: int(x)):
            res = (rmap[rn] or {}).get("result")
            if not _has_trifecta(res):
                res = fallback.get((int(sn), int(rn))) or res
            if not res:
                continue
            payouts = res.get("payouts") or {}
            tri = payouts.get("trifecta") or []
            if not tri:
                continue
            combo = tri[0].get("combination")
            pay = tri[0].get("amount")
            if not combo or pay in (None, 0):
                continue
            top3 = combo.split("-")
            if len(top3) != 3:
                continue
            try:
                # 級別は番組表側(レース直下のracers)にしかない。結果側のracersは
                # entry_number/course_number/start_timing/place_number/number/name の9項目だけ。
                # 枠番(entry_number)で引けるようにしておく。番組表が無い日は空のまま。
                ranks = {}
                prog_racers = (rmap[rn] or {}).get("racers") or {}
                for p in (prog_racers.values() if isinstance(prog_racers, dict) else prog_racers):
                    p = p or {}
                    if p.get("entry_number") is not None:
                        ranks[p["entry_number"]] = p
                boats = []
                racers = res.get("racers") or {}
                for en in sorted(racers, key=lambda x: int(x)):
                    b = racers[en] or {}
                    pg = ranks.get(b.get("entry_number")) or {}
                    boats.append({
                        "枠": b.get("entry_number"),
                        "登番": b.get("number"),
                        "氏名": b.get("name"),
                        "コース": b.get("course_number"),
                        "ST": b.get("start_timing"),
                        "着": b.get("place_number"),
                        "級別": pg.get("rank_number_source"),
                        "級別コード": pg.get("rank_number"),
                    })
                tech_no = res.get("technique_number")
                try:
                    tech_no = int(tech_no) if tech_no is not None else None
                except Exception:
                    tech_no = None
                races.append({
                    "場コード": "%02d" % int(res["stadium_number"]),
                    "レース": "%dR" % int(res["race_number"]),
                    "着順": combo,
                    "1着": int(top3[0]), "2着": int(top3[1]), "3着": int(top3[2]),
                    "三連単配当": int(pay),
                    "決まり手": TECHNIQUE.get(tech_no),
                    "払戻": _payouts(payouts),
                    "艇": boats,
                    "レース日": res.get("date"),
                    "風速": res.get("wind_speed"),
                    "風向コード": res.get("wind_direction_number"),
                    "波高": res.get("wave_height"),
                    "天候コード": res.get("weather_number"),
                    "気温": res.get("air_temperature"),
                    "水温": res.get("water_temperature"),
                })
            except Exception:
                continue
    return races


def v2_fallback(data, hd):
    """v1で欠けたレースがあるときだけv2を取りに行き、補えるレースを返す。"""
    miss = missing_races(data)
    if not miss:
        return {}
    data2 = fetch_json(hd, BASE_V2)
    if not data2:
        print("v2 fallback: no data for", hd, "/ v1 missing", len(miss))
        return {}
    cand = v2_results(data2)
    fb = {k: cand[k] for k in miss if k in cand and _has_trifecta(cand[k])}
    print("v2 fallback:", hd, "v1 missing", len(miss), "filled", len(fb),
          " ".join("%02d-%dR" % k for k in sorted(fb)))
    return fb


def write_results(data, hd):
    fb = v2_fallback(data, hd)
    void = {}
    for k, v in official_fallback(data, hd, fb, void).items():
        fb.setdefault(k, v)   # v2 で補えたレースは上書きしない
    races = to_races(data, fb)
    have = {(int(x["場コード"]), int(str(x["レース"]).rstrip("R"))) for x in races}
    # 結果が出ないことが確定したレース（中止・不成立）。「全レースそろった」の判定で、そろった側に数える（2026-10-29 けん）
    seiritsu = [{"場コード": "%02d" % k[0], "レース": "%dR" % k[1], "理由": void[k]}
                for k in sorted(void) if k not in have]
    venues = len(set(x["場コード"] for x in races))
    os.makedirs("results", exist_ok=True)
    outpath = os.path.join("results", "%s.json" % hd)
    obj = {"開催日": hd,
           "取得時刻": datetime.datetime.now().isoformat(timespec="seconds"),
           "レース数": len(races), "結果": races, "成立せず": seiritsu}
    with io.open(outpath, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    print("wrote", outpath, "races", len(races), "venues", venues)
    return len(races)


def main():
    hd_env = os.environ.get("HD", "").strip()
    if hd_env:
        days = [x.strip() for x in hd_env.replace("\u3001", ",").split(",") if x.strip()]
    else:
        # \u76f4\u8fd1N\u65e5\u306e\u7a93\uff08\u65e2\u5b9a3\uff09\u3067\u53d6\u5f97\u3002GitHub Actions\u306e\u30b9\u30b1\u30b8\u30e5\u30fc\u30eb\u9045\u5ef6\u3067\u767a\u706b\u304c
        # JST\u65e9\u671d\u306b\u305a\u308c\u8fbc\u307f\u300c\u5f53\u65e5\u306e\u307f\u300d\u3060\u3068\u7d42\u4e86\u76f4\u5f8c\u306e\u65e5\u3092\u90e8\u5206\u53d6\u5f97\u306e\u307e\u307e\u53d6\u308a\u3053\u307c\u3059\u554f\u984c\u3078\u306e\u5bfe\u7b56\u3002
        # \u30df\u30e9\u30fc\u306f\u78ba\u5b9a\u65e5\u306e\u5168\u7d50\u679c\u3092\u6301\u3064\u305f\u3081\u3001\u518d\u53d6\u5f97\u306f\u51aa\u7b49\uff08\u540c\u4e00\u30c7\u30fc\u30bf\u3067\u4e0a\u66f8\u304d\uff09\u3002
        win = max(1, int(os.environ.get("RESULTS_WINDOW", "3")))
        today = (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).date()
        days = [(today - datetime.timedelta(days=i)).strftime("%Y%m%d") for i in range(win)]

    for hd in days:
        data = fetch_json(hd)
        if not data:
            print("no data for", hd)
            continue
        write_results(data, hd)
        time.sleep(0.5)


if __name__ == "__main__":
    main()
