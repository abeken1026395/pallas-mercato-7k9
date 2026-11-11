# -*- coding: utf-8 -*-
# resultsLoop.py
# 当日の結果を、レースが終わるたびに取り込む見張り。updateResultsLive.yml から呼ばれ、1日を通して1本だけ走る。
#
# なぜ作ったか（2026-11-12）:
#   以前の取り込みは「毎時の定時」と「他のWFの完了への相乗り」で1回ずつ動く形だった。
#   GitHub の定時起動はほとんど飛ばされ（2026-11-11 は13回中2回）、相乗りも日中は数時間あく。
#   取得元 v1 は約10分おきに更新していたのに、こちらの results/ は最大4時間46分あいた。
#   そこで、1回起動したら夜まで走り続け、自分で時刻を見て取りに行く形にした。
#
# 動き:
#   1. 取得元 v1 の当日ファイルを読む（gh-pages の先頭のコミットが前回と同じなら読み直さない）。
#   2. 締切から OFFICIAL_AFTER_MIN 分たっても v1 に無いレースだけ、公式の結果ページを読む
#      （buildResults.py の予備をそのまま使う。一度読めたレースは読み直さない）。
#   3. 取得時刻を除いて前回と中身が同じなら何も書かない。変わったときだけ
#      results → 結果ページのデータ → 払戻CSV を作ってコミットし、配信WFを起動する。
#   4. 次に起きるのは「次のレースが締切から OFFICIAL_AFTER_MIN 分たつ時刻」。待ちのレースがあれば TICK_SEC ごと。
#   5. 全レースが取得元 v1 の版でそろう（結果あり・成立せず）か、JST 23:40 になったら終わる。
#      公式から補ったレースはコースとSTが空なので、v1 に載った時点で v1 の版に置き換わる（buildResults.py の決まり）。
#      ジョブの上限（6時間）の前に、自分で次の便を起動してから終わる。
#
# 二重に走らせない:
#   起動のきっかけは複数ある（定時・相乗り・手動・自分の中継）。走り始めに、同じWFで自分より先に
#   起動して終わっていない便があれば、何もせず終わる。
#
# 使い方（環境変数）:
#   HD                 日付(YYYYMMDD・カンマ区切り)。指定があればその日だけ1回取り込んで終わる（穴埋め用・従来どおり）
#   RESULTS_DRY_RUN    "1" ならコミット・push・配信の起動・中継をしない（確かめ用）
#   RESULTS_MAX_TICKS  この回数だけ回って終わる（確かめ用・既定0=無制限）
#   RESULTS_TICK_SEC   待ちのレースがあるときの間隔（既定180秒）
#   RESULTS_BUDGET_MIN この分数を超えたら次の便に中継して終わる（既定335分）
#   RELAY_FROM         中継元の run id（二重起動の判定から外す）
#   GH_TOKEN / GITHUB_REPOSITORY / GITHUB_RUN_ID / BR   Actions が渡す
import datetime
import glob
import io
import json
import os
import random
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import buildResults as br  # noqa: E402

V1_REPO = "https://github.com/boatraceopenapi/api"
V1_RAW = "https://raw.githubusercontent.com/boatraceopenapi/api/{sha}/docs/v1/{y}/{hd}.json"
WF_FILE = "updateResultsLive.yml"
DEPLOY_WF = "deployCloudflare.yml"

TICK_SEC = int(os.environ.get("RESULTS_TICK_SEC", "180"))
BUDGET_MIN = int(os.environ.get("RESULTS_BUDGET_MIN", "335"))
MAX_TICKS = int(os.environ.get("RESULTS_MAX_TICKS", "0") or 0)
DRY = os.environ.get("RESULTS_DRY_RUN", "") == "1"
EARLY_HOUR = 5        # これより前(JST)の起動は、従来どおり1回取り込んで終わる
LOOP_FROM = (8, 0)    # 見張りを始める時刻(JST)。これより前に起動したらここまで待つ
END_AT = (23, 40)     # 見張りを終える時刻(JST)
IDLE_MAX_SEC = 1800   # 待ちのレースが無いときの最長の待ち
V1_RECHECK_SEC = 600  # 全レースが入ったあと、v1 の版への置き換えを待つあいだの間隔（v1 の更新は約10分おき）


def now_jst():
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) + datetime.timedelta(hours=9)


def log(*a):
    print(now_jst().strftime("[%H:%M:%S]"), *a, flush=True)


def run(cmd, check=False, shell=False):
    """コマンドを実行して (終了コード, 出力) を返す。失敗で止めない（check=True のときだけ例外）。"""
    p = subprocess.run(cmd, shell=shell, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if check and p.returncode != 0:
        raise RuntimeError("failed: %s\n%s" % (cmd, p.stdout[-2000:]))
    return p.returncode, p.stdout


# ---------- 取得元 v1 ----------

def v1_head():
    """取得元 v1 の gh-pages の先頭コミット。取れなければ None。"""
    rc, out = run(["git", "ls-remote", V1_REPO, "refs/heads/gh-pages"])
    if rc != 0 or not out.strip():
        return None
    sha = out.split()[0]
    return sha if len(sha) == 40 else None


def fetch_v1(hd, st):
    """当日ファイルを返す。先頭コミットが前回と同じなら前回の中身をそのまま返す（通信しない）。
    コミット固定の住所で読むので、ブランチ指定の住所にある数分の古さが無い。
    先頭コミットが取れないときは従来の住所（ブランチ指定）で読む。"""
    sha = v1_head()
    if sha and sha == st.get("sha") and st.get("data") is not None:
        st["fresh"] = False
        return st["data"]
    data = None
    if sha:
        url = V1_RAW.format(sha=sha, y=hd[:4], hd=hd)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": br.UA})
            with urllib.request.urlopen(req, timeout=20) as r:
                raw = r.read()
            if raw and len(raw) >= 50:
                data = json.loads(raw.decode("utf-8"))
        except Exception as e:
            log("v1 fetch failed:", type(e).__name__, str(e)[:80])
    if data is None:
        data = br.fetch_json(hd)
        sha = None   # 古い版かもしれないので、次回も読み直す
    if data is not None:
        st["sha"] = sha
        st["data"] = data
        st["fresh"] = True
        st["fetches"] = st.get("fetches", 0) + 1
        return data
    st["fresh"] = False
    return st.get("data")


# ---------- 進み具合 ----------

def race_table(data):
    """{(場,R): 締切(datetime か None)}"""
    out = {}
    stadiums = ((data or {}).get("programs") or {}).get("stadiums") or {}
    for sn, v in stadiums.items():
        for rn, race in ((v or {}).get("races") or {}).items():
            try:
                closed = datetime.datetime.strptime((race or {}).get("closed_at") or "", "%Y-%m-%d %H:%M:%S")
            except Exception:
                closed = None
            try:
                out[(int(sn), int(rn))] = closed
            except Exception:
                continue
    return out


def done_keys(obj):
    """結果がある、または成立せずと分かったレース。"""
    out = set()
    for x in (obj.get("結果") or []) + (obj.get("成立せず") or []):
        try:
            out.add((int(x["場コード"]), int(str(x["レース"]).rstrip("R"))))
        except Exception:
            continue
    return out


def v1_pending(data):
    """取得元 v1 にまだ結果が無いレース（着順が1つも無いもの）。着順はあるのに3連単が無いレースは不成立なので数えない。"""
    out = set()
    stadiums = ((data or {}).get("programs") or {}).get("stadiums") or {}
    for sn, rn in br.missing_races(data):
        res = ((((stadiums.get(str(sn)) or {}).get("races") or {}).get(str(rn))) or {}).get("result") or {}
        if not any((b or {}).get("place_number") is not None for b in (res.get("racers") or {}).values()):
            out.add((sn, rn))
    return out


def same_content(obj, path):
    """取得時刻を除いて、いまのファイルと同じ中身か。ファイルが無い・読めないなら False。"""
    try:
        with io.open(path, encoding="utf-8") as f:
            old = json.load(f)
    except Exception:
        return False
    a = dict(obj)
    b = dict(old)
    a.pop("取得時刻", None)
    b.pop("取得時刻", None)
    return a == b


# ---------- 書き込みのあと ----------

def post_build():
    """結果ページのデータと払戻CSV・万舟率を作り直す（外部への通信なし）。失敗しても止めない。"""
    for cmd in ([sys.executable, "scripts/buildResultsSite.py"], [sys.executable, "scripts/buildPayoutsFromResults.py"]):
        rc, out = run(cmd)
        if rc != 0:
            log("post build failed:", " ".join(cmd), out[-400:])
    for f in sorted(glob.glob("scripts/build*ManRate.py")):
        rc, out = run([sys.executable, f])
        if rc != 0:
            log("post build failed:", f, out[-200:])


def commit_push():
    """変わった分をコミットして push する。push できたら True。何も変わっていなければ None。
    手順は以前の updateResultsLive.yml の commit ステップと同じ（先にコミット → rebase -X theirs → push を6回まで）。"""
    br_name = os.environ.get("BR") or "main"
    run("git add results/ docs/results/data/ 2>/dev/null || true", shell=True)
    # 払戻は別の add にする（まとめると1つ欠けただけで results まで0件 stage になる）
    run("git add docs/payouts/*Payouts.csv 2>/dev/null || true", shell=True)
    run("git add docs/payouts/*ManRate.json 2>/dev/null || true", shell=True)
    rc, _ = run(["git", "diff", "--staged", "--quiet"])
    if rc == 0:
        return None
    if DRY:
        _, out = run(["git", "diff", "--staged", "--stat"])
        log("DRY: コミットしない。変わったファイル:\n" + out[-600:])
        run(["git", "reset", "-q"])
        return None
    run(["git", "config", "user.name", "github-actions"])
    run(["git", "config", "user.email", "actions@github.com"])
    rc, out = run(["git", "commit", "-q", "-m", "auto: results live update"])
    if rc != 0:
        log("commit failed:", out[-300:])
        return False
    return push_retry(br_name)


def push_retry(br_name):
    # コミットに入らなかった変更が残っていると rebase が止まり、以後ずっと送れなくなる。
    # 残っていたら名前を記録して退避する（消さない。次の回の作り直しでまた出る）。
    rc, out = run(["git", "status", "--porcelain", "--untracked-files=no"])
    if out.strip():
        log("コミット外の変更を退避する:", " ".join(x[3:] for x in out.rstrip("\n").split("\n")[:10]))
        run(["git", "stash", "push", "-q"])
    for i in range(1, 7):
        run(["git", "fetch", "-q", "origin", br_name])
        rc, out = run(["git", "rebase", "-X", "theirs", "origin/" + br_name])
        if rc == 0:
            rc, out = run(["git", "push", "-q", "origin", "HEAD:" + br_name])
            if rc == 0:
                log("pushed (try %d)" % i)
                return True
        else:
            run(["git", "rebase", "--abort"])
        time.sleep(random.randint(3, 8))
    log("push retries exhausted（次の回でまとめて送る）")
    return False


def unpushed():
    """前の回で送れなかったコミットが残っているか。"""
    br_name = os.environ.get("BR") or "main"
    rc, out = run(["git", "rev-list", "--count", "origin/%s..HEAD" % br_name])
    try:
        return rc == 0 and int(out.strip()) > 0
    except ValueError:
        return False


def gh_api(args):
    if not os.environ.get("GH_TOKEN") or not os.environ.get("GITHUB_REPOSITORY"):
        return 1, "no token"
    return run(["gh", "api"] + args)


def dispatch(wf, inputs=None):
    """WF を起動する（GITHUB_TOKEN の push は他のWFを起動しないので、配信はここから起動する）。"""
    if DRY:
        log("DRY: 起動しない:", wf, inputs or "")
        return False
    args = ["-X", "POST", "repos/%s/actions/workflows/%s/dispatches" % (os.environ.get("GITHUB_REPOSITORY"), wf),
            "-f", "ref=" + (os.environ.get("BR") or "main")]
    for k, v in (inputs or {}).items():
        args += ["-f", "inputs[%s]=%s" % (k, v)]
    rc, out = gh_api(args)
    if rc != 0:
        log("dispatch failed:", wf, out[-300:])
    return rc == 0


def other_run_active():
    """同じWFで、自分より先に起動して終わっていない便の run id（無ければ None）。調べられなければ None（走る側に倒す）。"""
    me = os.environ.get("GITHUB_RUN_ID") or ""
    skip = {me, os.environ.get("RELAY_FROM") or ""}
    rc, out = gh_api(["repos/%s/actions/workflows/%s/runs?per_page=40" % (os.environ.get("GITHUB_REPOSITORY"), WF_FILE),
                      "--jq", '.workflow_runs[]|select(.status!="completed")|.id'])
    if rc != 0 or not me.isdigit():
        log("二重起動の確認ができなかった（走る側に倒す）:", out[-200:].strip())
        return None
    log("二重起動の確認: 終わっていない便", " ".join(out.split()) or "なし", "/ 自分", me)
    for line in out.split():
        if line.isdigit() and line not in skip and int(line) < int(me):
            return line
    return None


# ---------- 1回分 ----------

def one_day(hd, st, cache):
    """その日を1回取り込む。(書いたか, obj, data) を返す。"""
    data = fetch_v1(hd, st)
    if not data:
        log("no data for", hd)
        return False, None, None
    obj = br.build_obj(data, hd, cache)
    path = os.path.join("results", "%s.json" % hd)
    if same_content(obj, path):
        return False, obj, data
    br.write_obj(obj, hd)
    return True, obj, data


def publish(wrote):
    """書いた分（と、前に送れなかった分）を作り直してコミット・push し、配信を起動する。"""
    if wrote:
        post_build()
        ok = commit_push()
    elif unpushed() and not DRY:
        ok = push_retry(os.environ.get("BR") or "main")
    else:
        return
    if ok:
        dispatch(DEPLOY_WF)


def single_pass(days):
    wrote = False
    cache = {}
    for hd in days:
        w, _, _ = one_day(hd, {}, cache)
        wrote = wrote or w
        time.sleep(0.5)
    publish(wrote)


def next_wait(table, done, now):
    """次に起きるまでの秒数と、待ちのレース数（締切から OFFICIAL_AFTER_MIN 分たったのに結果が無い数）。"""
    after = datetime.timedelta(minutes=br.OFFICIAL_AFTER_MIN)
    due = [c + after for k, c in table.items() if k not in done and c is not None]
    overdue = sum(1 for t in due if t <= now)
    future = [t for t in due if t > now]
    wait = TICK_SEC if overdue else IDLE_MAX_SEC
    if future:
        wait = min(wait, max(60, int((min(future) - now).total_seconds()) + 5))
    return wait, overdue


def main():
    t0 = time.time()
    hd_env = (os.environ.get("HD") or "").strip()
    if hd_env:
        days = [x.strip() for x in hd_env.replace("、", ",").split(",") if x.strip()]
        log("日付指定の1回取り込み:", days)
        single_pass(days)
        return

    now = now_jst()
    today = now.strftime("%Y%m%d")
    yesterday = (now - datetime.timedelta(days=1)).strftime("%Y%m%d")
    if now.hour < EARLY_HOUR and not MAX_TICKS:
        log("JST %d時より前。前日と当日を1回取り込んで終わる" % EARLY_HOUR)
        single_pass([yesterday, today])
        return

    other = other_run_active()
    if other:
        log("先に起動した便が動いている（run %s）。何もせず終わる" % other)
        return

    log("見張りを始める。当日", today, "/ 間隔", TICK_SEC, "秒 / 公式は締切から", br.OFFICIAL_AFTER_MIN, "分後")
    cache = {}
    # 前日分を1回取り直す（夜のあいだに取得元が足した分を拾う）
    w, _, _ = one_day(yesterday, {}, cache)
    publish(w)

    start = now.replace(hour=LOOP_FROM[0], minute=LOOP_FROM[1], second=0, microsecond=0)
    end = now.replace(hour=END_AT[0], minute=END_AT[1], second=0, microsecond=0)
    while now_jst() < start and not MAX_TICKS:
        time.sleep(min(600, max(1, (start - now_jst()).total_seconds())))

    st = {}
    seen = set()
    ticks = 0
    while True:
        ticks += 1
        wrote, obj, data = one_day(today, st, cache)
        if obj is not None:
            table = race_table(data)
            done = done_keys(obj)
            now = now_jst()
            for k in sorted(done - seen):
                c = table.get(k)
                if c is not None and ticks > 1:
                    log("新しく入った %02d-%dR 締切から%.0f分" % (k[0], k[1], (now - c).total_seconds() / 60.0))
            seen |= done
            wait, overdue = next_wait(table, done, now)
            pend = v1_pending(data)
            if not overdue and not (set(table) - done) and pend:
                wait = min(wait, V1_RECHECK_SEC)   # 公式で埋めたレースを、v1 の版（コース・ST入り）に置き換えるのを待つ
            log("tick %d: %d/%dレース（v1 に未着 %d）待ち%d v1取得%d回 %s" % (
                ticks, len(done & set(table)), len(table), len(pend), overdue, st.get("fetches", 0),
                "書いた" if wrote else "変わらず"))
            publish(wrote)
            if table and not (set(table) - done) and not pend:
                log("全レースが取得元 v1 の版でそろった。終わる")
                break
        else:
            wait = IDLE_MAX_SEC
        if MAX_TICKS and ticks >= MAX_TICKS:
            log("確かめ用の回数に達した。終わる")
            break
        if now_jst() >= end:
            log("JST %02d:%02d を過ぎた。終わる" % END_AT)
            break
        if time.time() - t0 + wait > BUDGET_MIN * 60:
            log("ジョブの上限が近い。次の便に中継して終わる")
            dispatch(WF_FILE, {"relay_from": os.environ.get("GITHUB_RUN_ID") or ""})
            break
        time.sleep(wait)


if __name__ == "__main__":
    main()
