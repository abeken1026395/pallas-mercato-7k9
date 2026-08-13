# -*- coding: utf-8 -*-
# birthdayMark.py
# 誕生日マークの判定を1箇所に集約する。
#
# docs/data/racerStats.json の birth（和暦文字列・例「昭和59年1月8日」）を西暦に直し、
# 指定した開催日がその選手の誕生日かどうかを判定する。出走表（scrape_racers.py）と
# 見どころ（build_highlights.py）の両方がこれを呼ぶ。判定式を2箇所に書くと必ず
# 食い違うため、仕様変更はこのファイルだけで行う。
#
# 2月29日生まれは、平年は2月28日に成立させる（けん裁定 2026-08-14）。
# このとき注記「2月29日生まれ」を返し、深層で事実を明示できるようにする。
# 年齢は対象日の年から生年を引いた値（誕生日当日として数える）。
#
# 標準ライブラリのみ。pip 不要。
import datetime
import io
import json
import re

# 元号の基準年。西暦 = 基準年 + 元号年（昭和1年=1926 なので基準は1925）。
ERA_BASE = {"明治": 1867, "大正": 1911, "昭和": 1925, "平成": 1988, "令和": 2018}
_RE_BIRTH = re.compile(r"^(明治|大正|昭和|平成|令和)(\d+)年(\d+)月(\d+)日$")


def parse_birth(birth):
    """和暦の誕生日文字列を (西暦年, 月, 日) に直す。読めなければ None。"""
    if not birth:
        return None
    m = _RE_BIRTH.match(str(birth).strip())
    if not m:
        return None
    base = ERA_BASE.get(m.group(1))
    if base is None:
        return None
    return (base + int(m.group(2)), int(m.group(3)), int(m.group(4)))


def is_leap(year):
    """閏年なら True。"""
    return (year % 4 == 0 and year % 100 != 0) or year % 400 == 0


def mark_on(birth, target):
    """target（datetime.date）がその選手の誕生日なら (年齢, 注記) を返す。違えば None。

    注記は2月29日生まれを平年の2月28日で拾ったときだけ入る。通常は空文字列。
    """
    if target is None:
        return None
    ymd = parse_birth(birth)
    if ymd is None:
        return None
    by, bm, bd = ymd
    if target.year <= by:
        return None
    age = target.year - by
    if bm == target.month and bd == target.day:
        return (age, "")
    if (bm == 2 and bd == 29 and target.month == 2 and target.day == 28
            and not is_leap(target.year)):
        return (age, "2月29日生まれ")
    return None


def load_birth_map(path="docs/data/racerStats.json"):
    """登録番号 -> birth（和暦文字列）の辞書を返す。読めなければ空の辞書。

    誕生日マークは無くても他の表示が成立するため、例外は握って処理を止めない。
    """
    try:
        with io.open(path, "r", encoding="utf-8") as f:
            players = json.load(f).get("players", [])
    except Exception:
        return {}
    out = {}
    for p in players:
        no = p.get("no")
        birth = p.get("birth")
        if no and birth:
            out[str(no)] = birth
    return out


def ymd8_to_date(hd):
    """'YYYYMMDD' を datetime.date に直す。読めなければ None。"""
    try:
        return datetime.datetime.strptime(str(hd).strip(), "%Y%m%d").date()
    except Exception:
        return None
