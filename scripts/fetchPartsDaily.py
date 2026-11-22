# -*- coding: utf-8 -*-
# fetchPartsDaily.py  （PC の定時タスクで毎朝1回動かす）
# 2026-11-18 から公式（boatrace.jp）が GitHub Actions からの直前情報ページを 403 で拒否している。
# PC からは取れるので、前日分の部品交換をここで取り、リポジトリの data/partsDaily/<開催日>.json に
# GitHub の API で直接置く（PC の作業ツリーとブランチには触らない）。
# data/motorParts.json への取り込みは GitHub Actions 側の mergePartsDaily.py が行う。
#
# 取り方：scripts/fetchPartsExchange.py の main() をそのまま使う（行の形を収集行と同じにするため）。
#   - 1レースごとに2秒あける（相手の負荷を抑える）
#   - 403 が1件でも返ったらその日はそこで止め、置かない（拒否をかいくぐる取り直しはしない）
#   - 既に data/partsDaily/<開催日>.json が main にあれば何もしない（1日1回）
# 使い方:  python fetchPartsDaily.py [開催日YYYYMMDD]   （省略時は JST の前日）
# 終了コード: 0=置いた／既にある  2=止めた（403・取得0・検査落ち）  3=前提の不備
import os
import sys
import json
import time
import base64
import datetime
import subprocess
import importlib.util

REPO_DIR = os.environ.get("PARTS_REPO_DIR", r"C:\Users\USER\boatrace")
GH_REPO = "abeken1026395/pallas-mercato-7k9"
WORK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "work")
JST = datetime.timezone(datetime.timedelta(hours=9))
KEYS = ["jcd", "場名", "開催日", "rno", "枠", "登番", "氏名", "モーターNo", "節名",
        "部品交換", "展示タイム", "チルト", "プロペラ", "体重", "tenjiST",
        "tenjiCourse", "anteiban", "出典URL", "取得日時"]


def log(msg):
    os.makedirs(WORK, exist_ok=True)
    line = "[{}] {}".format(datetime.datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S"), msg)
    print(line)
    with open(os.path.join(WORK, "fetchPartsDaily.log"), "a", encoding="utf-8", newline="\n") as f:
        f.write(line + "\n")


def gh(args, stdin=None):
    p = subprocess.run(["gh"] + args, input=stdin, capture_output=True, text=True, encoding="utf-8")
    return p.returncode, p.stdout, p.stderr


def main():
    hd = sys.argv[1] if len(sys.argv) > 1 else (datetime.datetime.now(JST) - datetime.timedelta(days=1)).strftime("%Y%m%d")
    if len(hd) != 8 or not hd.isdigit():
        log("停止: 日付が不正 {}".format(hd))
        return 3
    path = "data/partsDaily/{}.json".format(hd)

    rc, out, err = gh(["api", "repos/{}/contents/{}?ref=main".format(GH_REPO, path), "--jq", ".sha"])
    if rc == 0 and out.strip():
        log("{}: main に既にある。何もしない".format(path))
        return 0

    src = os.path.join(REPO_DIR, "scripts", "fetchPartsExchange.py")
    if not os.path.isfile(src):
        log("停止: 収集処理が無い {}".format(src))
        return 3
    cwd0 = os.getcwd()
    os.chdir(REPO_DIR)  # results/ と pv2/programs/ を読むため（読むだけ。書くのは WORK の中だけ）
    try:
        os.environ["HD_OVERRIDE"] = hd
        os.environ["PARTS_SLEEP"] = "2"
        os.environ.setdefault("PARTS_TIMEOUT", "30")
        spec = importlib.util.spec_from_file_location("fpe", src)
        fpe = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fpe)
        tmp = os.path.join(WORK, "motorParts{}.json".format(hd))
        if os.path.exists(tmp):
            os.remove(tmp)
        fpe.OUT = tmp

        orig_fetch = fpe.fetch
        state = {"n": 0, "denied": 0}
        # 状態コードは requests.get を包んで自分で控える（作業ツリーの収集処理の版に依らない）
        last_status = {}
        orig_get = fpe.requests.get

        def get_keep_status(url, *a, **k):
            r = orig_get(url, *a, **k)
            last_status[url] = r.status_code
            return r

        fpe.requests.get = get_keep_status

        class Denied(Exception):
            pass

        def polite_fetch(url):
            final_url, html = orig_fetch(url)
            state["n"] += 1
            if last_status.get(url) == 403:
                state["denied"] += 1
                log("403 を受けたので、この日の取得をここで止める: {}".format(url))
                raise Denied()  # 以後1件も取りに行かない（保存もしない）
            return final_url, html

        fpe.fetch = polite_fetch
        try:
            fpe.main()
        except Denied:
            pass
        except SystemExit as e:
            log("収集処理が終了コード {} で止まった（取得0など）".format(e.code))
            return 2
    finally:
        os.chdir(cwd0)

    if state["denied"]:
        log("停止: 403 を受けた（{}件目）。置かない".format(state["n"]))
        return 2
    if not os.path.isfile(tmp):
        log("停止: 出力が無い")
        return 2
    recs = json.load(open(tmp, encoding="utf-8"))["records"]
    if not recs or any(r.get("開催日") != hd or list(r.keys()) != KEYS for r in recs):
        log("停止: 出力の検査に落ちた（{}行）".format(len(recs)))
        return 2
    keys = [(r["jcd"], str(r["rno"]), str(r["枠"])) for r in recs]
    if len(set(keys)) != len(keys):
        log("停止: 重複がある")
        return 2

    body = json.dumps({"hd": hd, "source": "boatrace.jp公式 直前情報（PC から取得）",
                       "records": recs}, ensure_ascii=False, indent=2).encode("utf-8")
    payload = json.dumps({
        "message": "部品交換：{} を PC から取得（{}行）".format(hd, len(recs)),
        "content": base64.b64encode(body).decode("ascii"),
        "branch": "main",
    })
    rc, out, err = gh(["api", "-X", "PUT", "repos/{}/contents/{}".format(GH_REPO, path), "--input", "-"], stdin=payload)
    if rc != 0:
        log("停止: 置けなかった {}".format(err.strip()[:300]))
        return 2
    log("{}: {}行を置いた（{}レース）".format(path, len(recs), len(set((r['jcd'], r['rno']) for r in recs))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
